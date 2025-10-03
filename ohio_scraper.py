#!/usr/bin/env python3
"""
Ohio Water System Data Scraper
Adapted from Scrapy to aiohttp for the Fantine infrastructure
"""

import asyncio
import aiohttp
import json
import logging
import os
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from uuid import uuid4
from typing import List, Dict, Any, Optional
import boto3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class OhioWaterResult:
    """Structure for Ohio water system data"""
    result_uuid: str
    state: str
    pwsid: str
    system_name: str
    unix_timestamp: str
    timestamp_utc: str
    result_id: str
    result_sample_type: str
    result_lab_sample_number: str
    result_sample_collection_timestamp: str
    result_sample_point: str
    result_sample_location: str
    result_presence_absence_indicator: str
    result_laboratory: str
    result_analyte_code: str
    result_analyte_name: str
    result_method_code: str
    result_less_than_indicator: str
    result_concentration_level: str
    result_unit: str
    result_mcl: str
    result_mcl_unit: str
    result_deviation: str
    result_detection: str
    result_analysis_begin_date: str
    result_analysis_end_date: str
    result_state_notified_date: str
    result_pws_notified_date: str
    result_exceeds_mcl: str
    result_monitoring_period_begin_date: str
    result_monitoring_period_end_date: str
    result_type: str  # 'coliform' or 'chemical'
    result_url: str
    result_facility_id: str
    result_facility_name: str
    result_ph_measure: str
    result_temperature_measure: str
    result_temperature_measure_code: str
    result_flow_rate_measure: str
    result_turbidity_measure: str
    result_collector_name: str
    result_microbial_count: str

class OhioWaterScraper:
    """Ohio Water System Data Scraper"""

    def __init__(self):
        self.state_abbrev = 'OH'
        self.results = []
        self.all_systems = []
        self.unix_timestamp = str(int(datetime.now().astimezone(timezone.utc).timestamp() * 1000))
        self.timestamp_utc = str(datetime.now().astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'))
        self.timestamp_for_file = str(datetime.now().astimezone(timezone.utc).strftime('%Y%m%d_%H%M'))

        # Ohio-specific URLs
        self.base_url = 'https://ohdwv.gecsws.com/'
        self.next_url = 'https://ohdwv.gecsws.com/sdwis/SearchResults'
        self.system_detail_url = 'https://ohdwv.gecsws.com/WaterSystem'
        self.coliform_results_url = 'https://ohdwv.gecsws.com/sdwis/SamplingColiformGrid'
        self.chemical_results_url = 'https://ohdwv.gecsws.com/sdwis/ChemicalGrid'
        self.chemical_details_url = 'https://ohdwv.gecsws.com/sdwis/SampleReportChemicalMain'
        
        # Pagination and system settings
        self.results_per_page = 225
        
        # Sample types used for both chemical and coliform searches
        self.sample_types = ['BB', 'CN', 'CO', 'DU', 'FB', 'FP', 'GR', 'MR', 'MS', 
                            'PE', 'RI', 'RL', 'RP', 'RT', 'SB', 'SL', 'ST', 'TG']

        # Create output directory
        self.output_dir = Path("/opt/fantine/results")
        self.output_dir.mkdir(exist_ok=True)

        # Headers to mimic browser requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"'
        }

    async def get_xsrf_token(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Get XSRF token from initial page"""
        try:
            async with session.get(self.base_url, headers=self.headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to get initial page: {response.status}")
                    return None
                
                # Extract XSRF token from cookies
                cookies = response.headers.get('Set-Cookie', '')
                xsrf_token = None
                
                if 'XSRF-TOKEN' in cookies:
                    start = cookies.find('XSRF-TOKEN=') + len('XSRF-TOKEN=')
                    end = cookies.find(';', start)
                    xsrf_token = cookies[start:end] if end > -1 else cookies[start:]
                
                if xsrf_token:
                    self.headers['X-XSRF-TOKEN'] = xsrf_token
                    logger.info("XSRF token obtained successfully")
                else:
                    logger.warning("XSRF token not found in response cookies")
                
                return xsrf_token
                
        except Exception as e:
            logger.error(f"Error getting XSRF token: {str(e)}")
            return None

    async def collect_all_systems(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Collect all water systems from Ohio database"""
        logger.info("Starting to collect all water systems...")
        
        # Filter for community water systems that are active
        filter_str = "D_PWS_FED_TYPE_CD eq 'C   ' and ACTIVITY_STATUS_CD eq 'A'"
        
        params = {
            '$orderby': 'ACTIVITY_STATUS_CD,NAME',
            '$skip': '0',
            '$top': str(self.results_per_page),
            '$filter': filter_str,
            '$count': 'true'
        }
        
        url = f"{self.next_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        
        all_systems = []
        skip = 0
        total_count = 0
        
        while True:
            current_params = params.copy()
            current_params['$skip'] = str(skip)
            current_url = f"{self.next_url}?{'&'.join(f'{k}={v}' for k, v in current_params.items())}"
            
            try:
                async with session.get(current_url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch systems batch: {response.status}")
                        break
                    
                    data = await response.json()
                    
                    if skip == 0:
                        total_count = data.get('@odata.count', 0)
                        logger.info(f"Total systems to collect: {total_count}")
                    
                    systems_batch = data.get('value', [])
                    all_systems.extend(systems_batch)
                    
                    logger.info(f"Collected batch of {len(systems_batch)} systems. Total so far: {len(all_systems)} of {total_count}")
                    
                    # Check if we need more systems
                    if len(systems_batch) < self.results_per_page or len(all_systems) >= total_count:
                        break
                    
                    skip += self.results_per_page
                    
            except Exception as e:
                logger.error(f"Error collecting systems batch: {str(e)}")
                break
        
        logger.info(f"Collected {len(all_systems)} systems total")
        return all_systems

    async def get_coliform_config(self, session: aiohttp.ClientSession, system_id: str) -> bool:
        """Get coliform configuration for a system"""
        formatted_system_id = f"{system_id}   "  # 3 spaces padding
        config_url = f"https://ohdwv.gecsws.com/api/Configuration/Configuration?n0={urllib.parse.quote(formatted_system_id)}&Id=MicrobialSamples"
        
        try:
            async with session.get(config_url, headers=self.headers) as response:
                if response.status == 200:
                    logger.info(f"Retrieved coliform configuration for system {system_id}")
                    return True
                else:
                    logger.warning(f"Failed to get coliform config for {system_id}: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error getting coliform config for {system_id}: {str(e)}")
            return False

    async def get_coliform_results(self, session: aiohttp.ClientSession, system_info: Dict[str, Any]) -> List[OhioWaterResult]:
        """Get coliform results for a system"""
        results = []
        
        # Get configuration first
        if not await self.get_coliform_config(session, system_info['system_id']):
            return results
        
        # Calculate date range (2 years from today)
        today = datetime.now()
        two_years_ago = today - timedelta(days=365*2)
        begin_date = two_years_ago.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        
        padded_system_id = f"{system_info['system_id']}+++"
        
        params = {
            '$orderby': 'CollectionDate DESC',
            'n0': padded_system_id,
            'bd': begin_date,
            'clfrm': 'true',
            'ed': end_date,
            'cmp': 'Y',
            'spt': '',
            'sampleDelay': '0',
            '$skip': '0',
            '$top': '1000',
            '$count': 'true'
        }
        
        # Add sample types
        sample_params = '&'.join([f'smp={st}' for st in self.sample_types])
        url = f"{self.coliform_results_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}&{sample_params}"
        
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 204 or not response.text:
                    logger.info(f"No coliform results for system {system_info['system_id']}")
                    return results
                
                data = await response.json()
                coliform_data = data.get('value', [])
                total_results = data.get('@odata.count', 0)
                
                logger.info(f"Found {len(coliform_data)} coliform results for {system_info['system_name']} ({system_info['system_id']})")
                
                for result in coliform_data:
                    # Get the first result from the Results array (for coliform data)
                    coliform_result = result.get('Results', [{}])[0]
                    
                    item = OhioWaterResult(
                        result_uuid=str(uuid4()),
                        state=self.state_abbrev,
                        pwsid=system_info['system_id'],
                        system_name=system_info['system_name'],
                        unix_timestamp=self.unix_timestamp,
                        timestamp_utc=self.timestamp_utc,
                        result_id=str(result.get('TSASAMPL_IS_NUMBER', '')),
                        result_sample_type=result.get('Type', ''),
                        result_lab_sample_number=result.get('SampleLabId', ''),
                        result_sample_collection_timestamp=result.get('CollectionDate', ''),
                        result_sample_point=result.get('SamplePoint', '').strip(),
                        result_sample_location=result.get('Location', '').strip(),
                        result_presence_absence_indicator=coliform_result.get('PresenceIndicator', ''),
                        result_laboratory=result.get('LaboratoryId', '').strip(),
                        result_analyte_code=coliform_result.get('AnalyteCode', ''),
                        result_analyte_name=coliform_result.get('AnalyteName', '').strip(),
                        result_method_code=coliform_result.get('Method', '').strip(),
                        result_less_than_indicator='',
                        result_concentration_level='',
                        result_unit='',
                        result_mcl='',
                        result_mcl_unit='',
                        result_deviation='',
                        result_detection='',
                        result_analysis_begin_date=coliform_result.get('AnalysisBeginDate', ''),
                        result_analysis_end_date=coliform_result.get('AnalysisEndDate', ''),
                        result_state_notified_date=coliform_result.get('StateNotifiedDate', ''),
                        result_pws_notified_date=coliform_result.get('PwsNotifiedDate', ''),
                        result_exceeds_mcl='',
                        result_monitoring_period_begin_date=result.get('MonPeriodBeginDate', ''),
                        result_monitoring_period_end_date=result.get('MonPeriodEndDate', ''),
                        result_type='coliform',
                        result_url=url,
                        result_facility_id='',
                        result_facility_name='',
                        result_ph_measure=str(result.get('PhMeasure', '')),
                        result_temperature_measure=str(result.get('TemperatureMeasure', '')),
                        result_temperature_measure_code=result.get('TemperatureMeasureCode', ''),
                        result_flow_rate_measure=str(result.get('FlowRateMeasure', '')),
                        result_turbidity_measure=str(result.get('TurbidityMeasure', '')),
                        result_collector_name=result.get('CollectorName', '').strip(),
                        result_microbial_count=coliform_result.get('MicrobialResultCount', '').strip()
                    )
                    results.append(item)
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting coliform results for {system_info['system_id']}: {str(e)}")
            return results

    async def get_chemical_config(self, session: aiohttp.ClientSession, system_id: str) -> bool:
        """Get chemical configuration for a system"""
        formatted_system_id = f"{system_id}   "  # 3 spaces padding
        config_url = f"https://ohdwv.gecsws.com/api/Configuration/Configuration?n0={urllib.parse.quote(formatted_system_id)}&Id=ChemicalSamples"
        
        try:
            async with session.get(config_url, headers=self.headers) as response:
                if response.status == 200:
                    logger.info(f"Retrieved chemical configuration for system {system_id}")
                    return True
                else:
                    logger.warning(f"Failed to get chemical config for {system_id}: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error getting chemical config for {system_id}: {str(e)}")
            return False

    async def get_chemical_results(self, session: aiohttp.ClientSession, system_info: Dict[str, Any]) -> List[OhioWaterResult]:
        """Get chemical results for a system"""
        results = []
        
        # Get configuration first
        if not await self.get_chemical_config(session, system_info['system_id']):
            return results
        
        # Calculate date range (3 years)
        today = datetime.now()
        three_years_ago = today - timedelta(days=365*3)
        begin_date = three_years_ago.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        
        padded_system_id = f"{system_info['system_id']}+++"
        
        params = {
            '$orderby': 'CollectionDate DESC',
            'n0': padded_system_id,
            'bd': begin_date,
            'ed': end_date,
            'cmp': 'Y',
            'spt': '',
            'sampleDelay': '0',
            '$skip': '0',
            '$top': '1000',
            '$count': 'true'
        }
        
        # Add sample types
        sample_params = '&'.join([f'smp={st}' for st in self.sample_types])
        url = f"{self.chemical_results_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}&{sample_params}"
        
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 204 or not response.text:
                    logger.info(f"No chemical samples for system {system_info['system_id']}")
                    return results
                
                data = await response.json()
                samples = data.get('value', [])
                total_samples = data.get('@odata.count', 0)
                
                logger.info(f"Found {len(samples)} chemical samples for {system_info['system_name']} ({system_info['system_id']})")
                
                # Process each sample and its analytes
                for sample in samples:
                    # Process each analyte result
                    for result in sample.get('Results', []):
                        item = OhioWaterResult(
                            result_uuid=str(uuid4()),
                            state=self.state_abbrev,
                            pwsid=system_info['system_id'],
                            system_name=system_info['system_name'],
                            unix_timestamp=self.unix_timestamp,
                            timestamp_utc=self.timestamp_utc,
                            result_id=str(sample.get('TSASAMPL_IS_NUMBER', '')),
                            result_sample_type=sample.get('Type', ''),
                            result_lab_sample_number=sample.get('SampleLabId', ''),
                            result_sample_collection_timestamp=sample.get('CollectionDate', ''),
                            result_sample_point=sample.get('SamplePoint', '').strip() if sample.get('SamplePoint') else '',
                            result_sample_location=sample.get('Location', '').strip() if sample.get('Location') else '',
                            result_presence_absence_indicator='',
                            result_laboratory=sample.get('LaboratoryId', '').strip() if sample.get('LaboratoryId') else '',
                            result_analyte_code=result.get('AnalyteCode', ''),
                            result_analyte_name=result.get('AnalyteName', '').strip() if result.get('AnalyteName') else '',
                            result_method_code=result.get('Method', '').strip() if result.get('Method') else '',
                            result_less_than_indicator=result.get('ResultLessInd', ''),
                            result_concentration_level=str(result.get('ResultMeasure', '')),
                            result_unit=result.get('ResultMeasureCode', '').strip() if result.get('ResultMeasureCode') else '',
                            result_mcl=str(result.get('MclMeasure', '')),
                            result_mcl_unit=result.get('MclCode', '').strip() if result.get('MclCode') else '',
                            result_deviation=str(result.get('Deviation', '')),
                            result_detection=result.get('Detection', '').strip() if result.get('Detection') else '',
                            result_analysis_begin_date=result.get('AnalysisBeginDate', ''),
                            result_analysis_end_date=result.get('AnalysisEndDate', ''),
                            result_state_notified_date=result.get('StateNotifiedDate', ''),
                            result_pws_notified_date=result.get('PwsNotifiedDate', ''),
                            result_exceeds_mcl=str(result.get('ExceedsMCL', '')),
                            result_monitoring_period_begin_date=sample.get('MonPeriodBeginDate', ''),
                            result_monitoring_period_end_date=sample.get('MonPeriodEndDate', ''),
                            result_type='chemical',
                            result_url=url,
                            result_facility_id=str(sample.get('FacilityId', '')),
                            result_facility_name=sample.get('FacilityName', '').strip() if sample.get('FacilityName') else '',
                            result_ph_measure='',
                            result_temperature_measure='',
                            result_temperature_measure_code='',
                            result_flow_rate_measure='',
                            result_turbidity_measure='',
                            result_collector_name='',
                            result_microbial_count=''
                        )
                        results.append(item)
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting chemical results for {system_info['system_id']}: {str(e)}")
            return results

    async def run(self):
        """Main scraping process"""
        logger.info("Starting Ohio Water System scraper...")

        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=self.headers) as session:
            # Step 1: Get XSRF token
            xsrf_token = await self.get_xsrf_token(session)
            if not xsrf_token:
                logger.error("Failed to get XSRF token. Cannot proceed.")
                return

            # Step 2: Collect all systems
            systems = await self.collect_all_systems(session)
            if not systems:
                logger.error("No systems collected. Cannot proceed.")
                return

            # Step 3: Process each system (limit to first 10 for testing)
            test_limit = min(10, len(systems))
            logger.info(f"Processing {test_limit} systems for testing...")

            for i, system in enumerate(systems[:test_limit]):
                if 'NUMBER0' not in system:
                    continue
                    
                system_id = system['NUMBER0'].strip()
                system_name = system.get('NAME', '').strip()
                system_status = system.get('ACTIVITY_STATUS_CD')
                system_type = system.get('D_PWS_FED_TYPE_CD', '').strip()
                system_county = system.get('D_PRIN_CNTY_SVD_NM', '').strip()

                system_info = {
                    'system_id': system_id,
                    'system_name': system_name,
                    'system_status': system_status,
                    'system_type': system_type,
                    'system_principal_county_served': system_county
                }

                logger.info(f"Processing system {i+1}/{test_limit}: {system_name} ({system_id})")

                # Get coliform results
                coliform_results = await self.get_coliform_results(session, system_info)
                self.results.extend(coliform_results)
                logger.info(f"Added {len(coliform_results)} coliform results")

                # Get chemical results
                chemical_results = await self.get_chemical_results(session, system_info)
                self.results.extend(chemical_results)
                logger.info(f"Added {len(chemical_results)} chemical results")

                # Add delay between systems
                await asyncio.sleep(1)

            # Save results
            await self._save_results()
            logger.info(f"Scraping completed! Total results: {len(self.results)}")

    async def _save_results(self):
        """Save Ohio water results to file and upload to Spaces"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"ohio_water_results_{timestamp}.json"

        # Convert results to dict format
        results_data = [asdict(result) for result in self.results]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to {output_file}")

        # Upload to DigitalOcean Spaces
        await self._upload_to_spaces(output_file)

        return output_file

    async def _upload_to_spaces(self, file_path: Path):
        """Upload file to DigitalOcean Spaces"""
        try:
            # Get credentials from environment variables
            spaces_key = os.getenv('DO_SPACES_KEY')
            spaces_secret = os.getenv('DO_SPACES_SECRET')
            spaces_endpoint = os.getenv('DO_SPACES_ENDPOINT', 'https://nyc3.digitaloceanspaces.com')
            spaces_bucket = os.getenv('DO_SPACES_BUCKET', 'fantine-bucket')
            
            logger.info(f"Uploading to Spaces - Key: {spaces_key[:10]}..., Secret: {spaces_secret[:10]}..., Bucket: {spaces_bucket}")
            
            if not spaces_key or not spaces_secret:
                logger.warning("DigitalOcean Spaces credentials not found. Skipping upload.")
                return
            
            # Create S3 client for DigitalOcean Spaces
            session = boto3.session.Session()
            client = session.client('s3',
                                  region_name='nyc3',
                                  endpoint_url=spaces_endpoint,
                                  aws_access_key_id=spaces_key,
                                  aws_secret_access_key=spaces_secret)
            
            # Upload file
            key = f"ohio-water-data/{file_path.name}"
            logger.info(f"Uploading file {file_path} to key: {key}")
            client.upload_file(str(file_path), spaces_bucket, key)
            
            # Generate public URL
            public_url = f"{spaces_endpoint}/{spaces_bucket}/{key}"
            logger.info(f"File uploaded to DigitalOcean Spaces: {public_url}")
            
            # Verify upload by listing objects
            try:
                response = client.list_objects_v2(Bucket=spaces_bucket, Prefix='ohio-water-data/')
                if 'Contents' in response:
                    logger.info(f"Verified upload - found {len(response['Contents'])} files in ohio-water-data/")
                    for obj in response['Contents']:
                        logger.info(f"  - {obj['Key']} ({obj['Size']} bytes)")
                else:
                    logger.warning("Upload verification failed - no files found in ohio-water-data/")
            except Exception as verify_error:
                logger.error(f"Upload verification failed: {str(verify_error)}")
            
        except Exception as e:
            logger.error(f"Failed to upload to DigitalOcean Spaces: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

async def main():
    """Main entry point for Ohio scraper"""
    scraper = OhioWaterScraper()
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())
