"""
API integration service for administrative divisions.
Integrates with external APIs like REST Countries, GeoNames, and other geographical data sources.
"""
import httpx
import asyncio
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from shared.models import AdministrativeDivision, DivisionQueryRequest, DivisionQueryResult
from shared.redis_manager import redis_manager

logger = logging.getLogger(__name__)


class AdminDivisionAPIService:
    """Service for fetching administrative division data from external APIs"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.cache_ttl = 3600  # 1 hour cache

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def query_rest_countries_api(self, request: DivisionQueryRequest) -> DivisionQueryResult:
        """Query REST Countries API for country-level data"""
        start_time = datetime.utcnow()
        cache_key = f"rest_countries:{request.query_type}:{request.search_term or request.iso_code}"

        # Check cache first
        if redis_manager.redis:
            cached_data = await redis_manager.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for REST Countries query: {cache_key}")
                return DivisionQueryResult.model_validate(json.loads(cached_data))

        try:
            divisions = []
            base_url = "https://restcountries.com/v3.1"

            if request.query_type == "by_name" and request.search_term:
                url = f"{base_url}/name/{request.search_term}"
            elif request.query_type == "by_code" and request.iso_code:
                url = f"{base_url}/alpha/{request.iso_code}"
            else:
                url = f"{base_url}/all"

            response = await self.client.get(url)
            response.raise_for_status()
            countries_data = response.json()

            # Convert to our format
            for country in countries_data[:request.limit]:
                # Extract data safely
                common_name = country.get("name", {}).get("common", "Unknown")
                official_name = country.get("name", {}).get("official", common_name)

                # Get alpha-2 code
                alpha2_code = country.get("cca2", "")
                alpha3_code = country.get("cca3", "")

                # Get coordinates
                latlng = country.get("latlng", [])
                lat = float(latlng[0]) if len(latlng) >= 2 else None
                lng = float(latlng[1]) if len(latlng) >= 2 else None

                # Get population and area
                population = country.get("population")
                area = country.get("area")

                # Get capital
                capitals = country.get("capital", [])
                capital = capitals[0] if capitals else None

                # Get timezones
                timezones = country.get("timezones", [])
                timezone = timezones[0] if timezones else None

                division = AdministrativeDivision(
                    id=alpha3_code or alpha2_code or common_name.replace(" ", "_").upper(),
                    name=common_name,
                    name_local=official_name if official_name != common_name else None,
                    type="country",
                    iso_code=alpha2_code,
                    parent_id=None,
                    level=0,
                    population=population,
                    area_km2=area,
                    capital=capital,
                    timezone=timezone,
                    latitude=lat,
                    longitude=lng,
                    metadata={
                        "alpha3_code": alpha3_code,
                        "currencies": country.get("currencies", {}),
                        "languages": country.get("languages", {}),
                        "region": country.get("region"),
                        "subregion": country.get("subregion"),
                        "source": "rest_countries_api"
                    }
                )
                divisions.append(division)

            end_time = datetime.utcnow()
            query_time_ms = (end_time - start_time).total_seconds() * 1000

            result = DivisionQueryResult(
                divisions=divisions,
                total_count=len(divisions),
                query_time_ms=query_time_ms,
                source="rest_countries_api",
                metadata={"api_url": url, "response_count": len(countries_data)}
            )

            # Cache the result
            if redis_manager.redis:
                await redis_manager.set(
                    cache_key,
                    json.dumps(result.model_dump(), default=str),
                    expire=self.cache_ttl
                )

            return result

        except httpx.HTTPError as e:
            logger.error(f"REST Countries API error: {e}")
            return DivisionQueryResult(
                divisions=[],
                total_count=0,
                query_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                source="rest_countries_api",
                metadata={"error": str(e)}
            )

    async def query_geonames_api(self, request: DivisionQueryRequest, username: str) -> DivisionQueryResult:
        """Query GeoNames API for detailed geographical data"""
        start_time = datetime.utcnow()
        cache_key = f"geonames:{request.query_type}:{request.search_term or ''}:{request.latitude or ''}:{request.longitude or ''}"

        # Check cache first
        if redis_manager.redis:
            cached_data = await redis_manager.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for GeoNames query: {cache_key}")
                return DivisionQueryResult.model_validate(json.loads(cached_data))

        try:
            divisions = []
            base_url = "http://api.geonames.org"

            params = {
                "username": username,
                "type": "json",
                "maxRows": request.limit
            }

            if request.query_type == "by_name" and request.search_term:
                url = f"{base_url}/searchJSON"
                params["name"] = request.search_term
                params["featureClass"] = "A"  # Administrative divisions
            elif request.query_type == "nearby" and request.latitude and request.longitude:
                url = f"{base_url}/findNearbyJSON"
                params["lat"] = request.latitude
                params["lng"] = request.longitude
                params["radius"] = request.radius_km or 100
            else:
                # Default to search
                url = f"{base_url}/searchJSON"
                params["featureClass"] = "A"

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            geonames = data.get("geonames", [])

            for place in geonames:
                # Map GeoNames feature codes to our division types
                feature_code = place.get("fcode", "")
                div_type = self._map_geonames_feature_code(feature_code)

                # Determine level based on feature code
                level = self._get_level_from_feature_code(feature_code)

                division = AdministrativeDivision(
                    id=f"geonames_{place.get('geonameId', '')}",
                    name=place.get("name", ""),
                    name_local=place.get("asciiName"),
                    type=div_type,
                    iso_code=place.get("countryCode"),
                    parent_id=None,  # Would need additional API calls to determine
                    level=level,
                    population=place.get("population"),
                    area_km2=None,  # Not provided by GeoNames
                    capital=None,
                    timezone=place.get("timezone", {}).get("timeZoneId"),
                    latitude=float(place.get("lat", 0)),
                    longitude=float(place.get("lng", 0)),
                    metadata={
                        "geoname_id": place.get("geonameId"),
                        "feature_class": place.get("fcl"),
                        "feature_code": feature_code,
                        "country_name": place.get("countryName"),
                        "admin1_code": place.get("adminCode1"),
                        "admin2_code": place.get("adminCode2"),
                        "source": "geonames_api"
                    }
                )
                divisions.append(division)

            end_time = datetime.utcnow()
            query_time_ms = (end_time - start_time).total_seconds() * 1000

            result = DivisionQueryResult(
                divisions=divisions,
                total_count=len(divisions),
                query_time_ms=query_time_ms,
                source="geonames_api",
                metadata={"api_url": url, "response_count": len(geonames)}
            )

            # Cache the result
            if redis_manager.redis:
                await redis_manager.set(
                    cache_key,
                    json.dumps(result.model_dump(), default=str),
                    expire=self.cache_ttl
                )

            return result

        except httpx.HTTPError as e:
            logger.error(f"GeoNames API error: {e}")
            return DivisionQueryResult(
                divisions=[],
                total_count=0,
                query_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                source="geonames_api",
                metadata={"error": str(e)}
            )

    def _map_geonames_feature_code(self, feature_code: str) -> str:
        """Map GeoNames feature codes to our division types"""
        mapping = {
            "PCLI": "country",
            "ADM1": "state",
            "ADM2": "county",
            "ADM3": "municipality",
            "ADM4": "district",
            "PPL": "city",
            "PPLA": "state_capital",
            "PPLC": "capital",
            "PPLA2": "county_seat",
        }
        return mapping.get(feature_code, "administrative_division")

    def _get_level_from_feature_code(self, feature_code: str) -> int:
        """Determine administrative level from GeoNames feature code"""
        level_mapping = {
            "PCLI": 0,  # Country
            "ADM1": 1,  # State/Province
            "ADM2": 2,  # County
            "ADM3": 3,  # Municipality
            "ADM4": 4,  # District
            "PPL": 5,   # City
            "PPLA": 5,  # State capital
            "PPLC": 5,  # Capital
            "PPLA2": 5, # County seat
        }
        return level_mapping.get(feature_code, 3)

    async def aggregate_multi_source_query(
        self,
        request: DivisionQueryRequest,
        geonames_username: Optional[str] = None
    ) -> DivisionQueryResult:
        """Query multiple APIs and aggregate results"""
        start_time = datetime.utcnow()
        all_divisions = []
        sources_used = []
        errors = []

        # Query REST Countries for country-level data
        if request.level is None or request.level == 0:
            try:
                rest_countries_result = await self.query_rest_countries_api(request)
                all_divisions.extend(rest_countries_result.divisions)
                sources_used.append("rest_countries_api")
            except Exception as e:
                errors.append(f"REST Countries API: {str(e)}")

        # Query GeoNames if username is provided
        if geonames_username:
            try:
                geonames_result = await self.query_geonames_api(request, geonames_username)
                all_divisions.extend(geonames_result.divisions)
                sources_used.append("geonames_api")
            except Exception as e:
                errors.append(f"GeoNames API: {str(e)}")

        # Remove duplicates based on name and coordinates
        unique_divisions = self._deduplicate_divisions(all_divisions)

        # Apply limit
        limited_divisions = unique_divisions[:request.limit]

        end_time = datetime.utcnow()
        query_time_ms = (end_time - start_time).total_seconds() * 1000

        return DivisionQueryResult(
            divisions=limited_divisions,
            total_count=len(unique_divisions),
            query_time_ms=query_time_ms,
            source="aggregated_apis",
            metadata={
                "sources_used": sources_used,
                "errors": errors,
                "duplicate_count": len(all_divisions) - len(unique_divisions)
            }
        )

    def _deduplicate_divisions(self, divisions: List[AdministrativeDivision]) -> List[AdministrativeDivision]:
        """Remove duplicate divisions based on name and approximate coordinates"""
        seen = set()
        unique_divisions = []

        for div in divisions:
            # Create a key for deduplication
            key_parts = [div.name.lower()]
            if div.latitude and div.longitude:
                # Round coordinates to reduce precision for matching
                key_parts.extend([
                    str(round(div.latitude, 2)),
                    str(round(div.longitude, 2))
                ])

            key = "|".join(key_parts)

            if key not in seen:
                seen.add(key)
                unique_divisions.append(div)

        return unique_divisions


# Singleton instance
admin_division_api = AdminDivisionAPIService()