from __future__ import annotations

import json
import time
from typing import Any, Literal, List

import requests
from pathlib import Path
from bs4 import BeautifulSoup


SEARCH_URL = "https://www.sos.ms.gov/adminsearch/AdminSearchService.asmx/CodeSearch"
WARMUP_URL = "https://www.sos.ms.gov/adminsearch/default.aspx"
base_download = "https://www.sos.ms.gov/adminsearch/ACCode/"

agency_html = """<select id="cAgencySearch" style="width:500px;"><option value=""></option><option value="54 ">Title 1 - SECRETARY OF STATE</option><option value="84 ">Title 2 - BOARD OF ANIMAL HEALTH</option><option value="157 ">Title 2 - MISSISSIPPI COOPERATIVE EXTENSION SERVICE</option><option value="78 ">Title 2 - MISSISSIPPI DEPARTMENT OF AGRICULTURE AND COMMERCE</option><option value="65 ">Title 2 - MISSISSIPPI FAIR COMMISSION</option><option value="137 ">Title 2 - MISSISSIPPI LAND WATER AND TIMBER RESOURCES BOARD</option><option value="197 ">Title 2 - RICE PROMOTION BOARD</option><option value="176 ">Title 2 - SOYBEAN PROMOTION BOARD</option><option value="27 ">Title 2 - STATE FORESTRY COMMISSION</option><option value="55 ">Title 2 - STATE SOIL AND WATER CONSERVATION COMMISSION</option><option value="83 ">Title 3 - ATTORNEY GENERAL</option><option value="56 ">Title 4 - AUDITOR</option><option value="1 ">Title 5 - DEPARTMENT OF BANKING AND CONSUMER FINANCE</option><option value="154 ">Title 6 - MISSISSIPPI BUSINESS FINANCE CORPORATION</option><option value="161 ">Title 6 - MISSISSIPPI DEVELOPMENT AUTHORITY</option><option value="135 ">Title 6 - MISSISSIPPI DEVELOPMENT BANK</option><option value="41 ">Title 6 - PEARL RIVER BASIN DEVELOPMENT DISTRICT</option><option value="64 ">Title 7 - DEPARTMENT OF EDUCATION</option><option value="88 ">Title 8 - STATE INSTITUTIONS OF HIGHER LEARNING</option><option value="11 ">Title 9 - MISSISSIPPI COMMUNITY COLLEGE BOARD</option><option value="235 ">Title 10 - CHARTER SCHOOL AUTHORIZER BOARD</option><option value="117 ">Title 10 - COMMISSION ON COLLEGE ACCREDITATION</option><option value="46 ">Title 10 - COMMISSION ON PROPRIETARY SCHOOL AND COLLEGE REGISTRATION</option><option value="212 ">Title 10 - EDNET INSTITUTE</option><option value="22 ">Title 10 - MISSISSIPPI AUTHORITY FOR EDUCATIONAL TELEVISION</option><option value="234 ">Title 10 - MS POST-SECONDARY EDUCATION FINANCIAL ASSISTANCE BOARD</option><option value="236 ">Title 10 - STATE LONGITUDINAL DATA SYSTEMS GOVERNING BOARD</option><option value="213 ">Title 11 - HAZARDOUS WASTE FACILITY SITING AUTHORITY</option><option value="14 ">Title 11 - MISSISSIPPI DEPARTMENT OF ENVIRONMENTAL QUALITY</option><option value="26 ">Title 12 - DEPARTMENT OF FINANCE AND ADMINISTRATION</option><option value="111 ">Title 13 - MISSISSIPPI GAMING COMMISSION</option><option value="38 ">Title 14 - OFFICE OF THE GOVERNOR</option><option value="15 ">Title 15 - MISSISSIPPI DEPARTMENT OF HEALTH</option><option value="93 ">Title 15 - MISSISSIPPI HOSPITAL EQUIPMENT AND FACILITIES AUTHORITY</option><option value="81 ">Title 16 - ARCHIVES AND HISTORY</option><option value="241 ">Title 16 - MISSISSIPPI ARTS COMMISSION</option><option value="33 ">Title 16 - MISSISSIPPI LIBRARY COMMISSION</option><option value="130 ">Title 17 - MISSISSIPPI HOME CORPORATION</option><option value="193 ">Title 18 - COMMISSION ON THE STATUS OF WOMEN</option><option value="243 ">Title 18 - MISSISSIPPI DEPARTMENT OF CHILD PROTECTION SERVICES </option><option value="16 ">Title 18 - MISSISSIPPI DEPARTMENT OF HUMAN SERVICES</option><option value="214 ">Title 18 - TANF IMPLEMENTATION COUNCIL</option><option value="29 ">Title 19 - MISSISSIPPI DEPARTMENT OF INSURANCE</option><option value="232 ">Title 19 - MISSISSIPPI FIRE PERSONNEL MINIMUM STANDARDS AND CERTIFICATION BOARD</option><option value="24 ">Title 20 - MISSISSIPPI DEPARTMENT OF EMPLOYMENT SECURITY</option><option value="237 ">Title 20 - STATE WORKFORCE INVESTMENT BOARD</option><option value="76 ">Title 20 - WORKERS COMPENSATION COMMISSION</option><option value="79 ">Title 21 - COMMISSION ON JUDICIAL PERFORMANCE</option><option value="87 ">Title 21 - CRIME VICTIMS COMPENSATION PROGRAM</option><option value="99 ">Title 21 - MISSISSIPPI ETHICS COMMISSION</option><option value="73 ">Title 21 - TORT CLAIMS BOARD</option><option value="94 ">Title 22 - MISSISSIPPI DEPARTMENT OF MARINE RESOURCES</option><option value="20 ">Title 23 - DIVISION OF MEDICAID</option><option value="17 ">Title 24 - MISSISSIPPI DEPARTMENT OF MENTAL HEALTH</option><option value="98 ">Title 25 - MILITARY DEPARTMENT</option><option value="71 ">Title 25 - VETERANS AFFAIRS BOARD</option><option value="74 ">Title 25 - VETERANS HOME PURCHASE BOARD</option><option value="67 ">Title 26 - STATE OIL AND GAS BOARD</option><option value="113 ">Title 27 - PERSONAL SERVICES CONTRACT REVIEW BOARD</option><option value="47 ">Title 27 - PUBLIC EMPLOYEES RETIREMENT SYSTEM</option><option value="68 ">Title 27 - STATE PERSONNEL BOARD</option><option value="49 ">Title 28 - BILOXI PORT COMMISSION</option><option value="216 ">Title 28 - CLAIBORNE COUNTY PORT COMMISSION</option><option value="217 ">Title 28 - COAHOMA COUNTY PORT COMMISSION</option><option value="222 ">Title 28 - GREENVILLE PORT COMMISSION</option><option value="43 ">Title 28 - GULFPORT STATE PORT AUTHORITY</option><option value="218 ">Title 28 - HANCOCK COUNTY PORT COMMISSION</option><option value="219 ">Title 28 - HATTIESBURG-LAUREL AIRPORT AUTHORITY</option><option value="30 ">Title 28 - JACKSON COUNTY PORT AUTHORITY</option><option value="220 ">Title 28 - PASCAGOULA PORT COMMISSION</option><option value="221 ">Title 28 - WARREN COUNTY PORT COMMISSION</option><option value="223 ">Title 28 - WAYPORT AUTHORITY</option><option value="181 ">Title 28 - YAZOO COUNTY PORT COMMISSION</option><option value="179 ">Title 28 - YELLOW CREEK STATE INLAND PORT AUTHORITY</option><option value="77 ">Title 29 - MISSISSIPPI DEPARTMENT OF CORRECTIONS</option><option value="97 ">Title 29 - MISSISSIPPI PRISON INDUSTRIES CORPORATION</option><option value="39 ">Title 29 - PAROLE BOARD</option><option value="239 ">Title 30 - AUTISM BOARD</option><option value="102 ">Title 30 - BOARD OF AGRICULTURAL AVIATION</option><option value="106 ">Title 30 - BOARD OF AUCTIONEERS</option><option value="57 ">Title 30 - BOARD OF BAR ADMISSIONS</option><option value="114 ">Title 30 - BOARD OF EXAMINERS FOR SOCIAL WORKERS &amp; FAMILY THERAPIST</option><option value="44 ">Title 30 - BOARD OF LICENSURE FOR PROFESSIONAL ENGINEERS AND LAND SURVEYORS</option><option value="4 ">Title 30 - BOARD OF NURSING HOME ADMINISTRATORS</option><option value="45 ">Title 30 - BOARD OF POLYGRAPH EXAMINERS</option><option value="6 ">Title 30 - BOARD OF PUBLIC ACCOUNTANCY</option><option value="7 ">Title 30 - BOARD OF REGISTRATION FOR FORESTERS</option><option value="8 ">Title 30 - BOARD OF VETERINARY MEDICINE</option><option value="119 ">Title 30 - COMMERCIAL RADIO SERVICE BOARD</option><option value="224 ">Title 30 - HOME INSPECTOR REGULATORY BOARD</option><option value="105 ">Title 30 - MISSISSIPPI ATHLETIC COMMISSION</option><option value="91 ">Title 30 - MISSISSIPPI BOARD OF NURSING</option><option value="5 ">Title 30 - MISSISSIPPI BOARD OF PSYCHOLOGY</option><option value="107 ">Title 30 - MISSISSIPPI COMMISSION ON CONTINUING LEGAL EDUCATION</option><option value="37 ">Title 30 - MISSISSIPPI MOTOR VEHICLE COMMISSION</option><option value="242 ">Title 30 - MISSISSIPPI STATE BOARD OF COSMETOLOGY AND BARBERING</option><option value="60 ">Title 30 - MISSISSIPPI STATE BOARD OF DENTAL EXAMINERS</option><option value="89 ">Title 30 - MISSISSIPPI STATE BOARD OF EXAMINERS FOR LICENSED PROFESSIONAL COUNSELORS</option><option value="50 ">Title 30 - REAL ESTATE APPRAISER LICENSING AND CERTIFICATION BOARD</option><option value="51 ">Title 30 - REAL ESTATE COMMISSION</option><option value="82 ">Title 30 - STATE BOARD OF ARCHITECTURE</option><option value="58 ">Title 30 - STATE BOARD OF BARBER EXAMINERS</option><option value="86 ">Title 30 - STATE BOARD OF CHIROPRACTIC EXAMINERS</option><option value="59 ">Title 30 - STATE BOARD OF CONTRACTORS</option><option value="61 ">Title 30 - STATE BOARD OF FUNERAL SERVICES</option><option value="133 ">Title 30 - STATE BOARD OF GEOLOGISTS</option><option value="138 ">Title 30 - STATE BOARD OF MASSAGE THERAPY</option><option value="90 ">Title 30 - STATE BOARD OF MEDICAL LICENSURE</option><option value="62 ">Title 30 - STATE BOARD OF OPTOMETRY</option><option value="63 ">Title 30 - STATE BOARD OF PHARMACY</option><option value="165 ">Title 30 - STATE BOARD OF PHYSICAL THERAPY</option><option value="100 ">Title 31 - BOARD OF EMERGENCY TELECOMUNICATIONS STANDARDS &amp; TRAINING</option><option value="3 ">Title 31 - BOARD OF LAW ENFORCEMENT OFFICER STANDARDS TRAINING</option><option value="192 ">Title 31 - BOARD ON JAIL OFFICER STANDARDS AND TRAINING</option><option value="225 ">Title 31 - CRIME LABORATORY</option><option value="18 ">Title 31 - DEPARTMENT OF PUBLIC SAFETY</option><option value="31 ">Title 31 - MEDICAL EXAMINER</option><option value="32 ">Title 31 - MISSISSIPPI EMERGENCY MANAGEMENT AGENCY</option><option value="139 ">Title 32 - MISSISSIPPI INDUSTRIES FOR THE BLIND</option><option value="52 ">Title 32 - REHABILITATION SERVICES</option><option value="112 ">Title 33 - LOCAL GOVERMENTS AND RURAL WATER SYSTEMS IMPROVEMENTS BOARD</option><option value="40 ">Title 33 - PAT HARRISON WATERWAY DISTRICT</option><option value="42 ">Title 33 - PEARL RIVER VALLEY WATER SUPPLY DISTRICT</option><option value="178 ">Title 33 - TENN-TOMBIGBEE WATERWAY DEVELOPMENT AUTHORITY</option><option value="72 ">Title 33 - TOMBIGBEE RIVER VALLEY WATER MANAGEMENT DISTRICT</option><option value="240 ">Title 33 - YAZOO MISSISSIPPI DELTA JOINT WATER MANAGEMENT DISTRICT</option><option value="208 ">Title 35 - MISSISSIPPI BOARD OF TAX APPEALS</option><option value="69 ">Title 35 - MISSISSIPPI DEPARTMENT OF REVENUE</option><option value="244 ">Title 36 - CYBER SECURITY REVIEW BOARD</option><option value="233 ">Title 36 - MISSISSIPPI ELECTRONIC RECORDING COMMISSION</option><option value="10 ">Title 36 - MISSISSIPPI INFORMATION TECHNOLOGY SERVICES</option><option value="227 ">Title 36 - WIRELESS COMMUNICATION COMMISSION</option><option value="228 ">Title 37 - ARKANSAS-MISSISSIPPI GREAT RIVER BRIDGE AUTHORITY</option><option value="183 ">Title 37 - HARRISON COUNTY PARKWAY COMMISSION</option><option value="229 ">Title 37 - HIGHWAY 82 FOUR LANE CONSTRUCTION AUTHORITY</option><option value="35 ">Title 37 - MISSISSIPPI DEPARTMENT OF TRANSPORTATION</option><option value="230 ">Title 37 - TRANSPORTATION ARBITRATION BOARD</option><option value="70 ">Title 38 - TREASURY DEPARTMENT</option><option value="48 ">Title 39 - PUBLIC SERVICE COMMISSION</option><option value="238 ">Title 39 - UNDERGROUND FACILITIES DAMAGE PREVENTION BOARD</option><option value="199 ">Title 40 - CIVIL WAR BATTLEFIELD COMMISSION</option><option value="231 ">Title 40 - DESOTO TRAIL COMMISSION</option><option value="75 ">Title 40 - WILDLIFE, FISHERIES, AND PARKS</option></select>"""


DEFAULT_BROWSER_UA = (
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
)



def get_agency_pairs(html: str = agency_html) -> list[tuple[str,str]]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    sel = soup.select_one("select#cAgencySearch")
    if not sel:
        return []
    pairs = []
    for opt in sel.find_all("option"):
        val = (opt.get("value") or "").strip()
        text = opt.get_text(strip=True)
        if text:
            pairs.append((val, text))
    return pairs

def code_search(
	tmpAgency: str | int,
	*,
	url: str = SEARCH_URL,
	timeout_s: float = 30.0,
	output: Literal["text", "json"] = "text",
	session: requests.Session | None = None,
	user_agent: str = DEFAULT_BROWSER_UA,
	warmup: bool = True,
	retries: int = 2,
) -> str | dict[str, Any]:
	"""POST to the Mississippi SOS `CodeSearch` endpoint and return its output.

	This is intentionally simple: a lightweight warmup GET (optional) and a JSON
	POST. No cookie injection; a minimal retry loop is included.
	"""

	payload: dict[str, Any] = {
		"tmpSubject": "",
		"tmpAgency": str(tmpAgency),
		"tmpPartRange1": "",
		"tmpPartRange2": "",
		"tmpRuleSum": "",
		"tmpOrder": "PartNo",
		"tmpOrderDirec": "Ascending",
		"tmpSearchDate1": "",
		"tmpSearchDate2": "",
		"tmpDateType": "0",
	}

	client = session or requests.Session()
	client.headers.update(
		{
			"User-Agent": user_agent,
			"Accept": "*/*",
			"Accept-Language": "en-US,en;q=0.9",
			"Origin": "https://www.sos.ms.gov",
			"Referer": WARMUP_URL,
			"X-Requested-With": "XMLHttpRequest",
			"Content-Type": "application/json; charset=UTF-8",
		}
	)

	if warmup:
		try:
			client.get(WARMUP_URL, timeout=timeout_s)
		except requests.RequestException:
			# ignore warmup failures; proceed to POST
			pass

	last_exc: Exception | None = None
	for attempt in range(retries + 1):
		try:
			resp = client.post(url, json=payload, timeout=timeout_s)
			resp.raise_for_status()
			break
		except requests.RequestException as exc:
			last_exc = exc
			if attempt >= retries:
				raise
			time.sleep(1 + attempt)
	else:
		raise last_exc or RuntimeError("Request failed")

	if output == "text":
		return resp.text

	try:
		return resp.json()
	except Exception as exc:
		raise ValueError("Response was not valid JSON; use output='text' to inspect") from exc

def parse_code_search_result(resp: str | dict) -> tuple[int, list[str]]:
	"""Parse a `code_search` response and return (count, list_of_filenames).

	The service returns JSON like {"d":"rec1^rec2^...|15"} where each record
	is tilde-delimited (~). The filename (PDF) is typically the last ~-delimited
	field in each record. This function extracts those filenames.

	Args:
		resp: Response from `code_search` (raw text or parsed dict).

	Returns:
		A tuple of (count, list_of_filenames).
	"""
	# Accept dict returned by requests.json(). If a raw JSON text string
	# (e.g. '{"d":"...|0"}') is passed, try to decode it and extract
	# the inner `d` value. Otherwise fall back to the literal string.
	if isinstance(resp, dict):
		val = resp.get("d") or resp.get("D") or ""
		if not isinstance(val, str):
			val = str(val)
	else:
		# resp may be a text string containing the JSON object; attempt to
		# decode that and extract `d` so we don't treat the whole JSON blob
		# as a single record.
		if isinstance(resp, str):
			s = resp.strip()
			if s.startswith("{") or '"d"' in s or '"D"' in s:
				try:
					parsed = json.loads(s)
					if isinstance(parsed, dict):
						val = parsed.get("d") or parsed.get("D") or ""
						if not isinstance(val, str):
							val = str(val)
					else:
						val = s
				except Exception:
					val = s
			else:
				val = s
		else:
			val = str(resp)

	val = val.strip()
	# If the service appends a global suffix like '|15' indicating total
	# number of documents, capture it and remove it from the payload string.
	total_count: int | None = None
	if '|' in val:
		parts = val.rsplit('|', 1)
		if len(parts) == 2 and parts[1].strip().isdigit():
			total_count = int(parts[1].strip())
			val = parts[0]

	records = [r for r in val.split('^') if r.strip()]
	filenames: list[str] = []
	for rec in records:
		if '~' in rec:
			candidate = rec.rsplit('~', 1)[-1].strip()
		else:
			candidate = rec.strip()
		# Remove surrounding punctuation
		candidate = candidate.strip(' \"\'{}[]')
		# If a pipe and a numeric suffix was included (e.g. '00000765c.pdf|15'),
		# split it off and keep only the filename part.
		if '|' in candidate:
			candidate = candidate.split('|', 1)[0].strip()
		if candidate:
			filenames.append(candidate)

	# If the service provided the total count as a suffix, return it.
	if total_count is not None:
		return total_count, filenames
    
	return len(filenames), filenames

def download_document(url: str, dest_dir: str | Path = "./documents", filename: str | None = None) -> Path:
	"""Download `url` into `dest_dir` and return saved Path.

	If `filename` is provided, use it for the saved file (sanitized).
	Otherwise the filename is derived from the URL.
	"""
	dirpath = Path(dest_dir)
	dirpath.mkdir(parents=True, exist_ok=True)
	resp = requests.get(url, stream=True)
	resp.raise_for_status()

	if filename:
		# sanitize provided filename to avoid directory traversal
		out_name = Path(filename).name
	else:
		out_name = url.rstrip("/ ").rsplit("/", 1)[-1]

	if not out_name:
		raise ValueError("Could not determine filename for saving the document")

	filepath = dirpath / out_name
	with open(filepath, "wb") as fh:
		for chunk in resp.iter_content(8192):
			if chunk:
				fh.write(chunk)
	return filepath

total_documents = 0

if __name__ == "__main__":
	agency_pairs = get_agency_pairs()
	for value, title in agency_pairs:
		print(f"Collecting and downloading documents for {value}: {title}")
		resp = code_search(value, output="text")
		count, filenames = parse_code_search_result(resp)
		total_documents += count
		print(f"  Found {count} documents")
		for fname in filenames:
			doc_url = base_download + fname
			try:
				saved_path = download_document(doc_url, filename=fname)
			except Exception as exc:
				print(f"    Failed to download {fname}: {exc}")
				continue
			print(f"    Saved to {saved_path}")
	print(f"Total documents downloaded: {total_documents}")
