from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATES_DIR = DATA_DIR / "states"

STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

STATE_EMERGENCY_AGENCY_LINKS = {
    "AL": ("Alabama Emergency Management Agency", "https://ema.alabama.gov/"),
    "AK": ("Alaska Division of Homeland Security and Emergency Management", "https://ready.alaska.gov/"),
    "AZ": ("Arizona Division of Emergency Management", "https://dema.az.gov/"),
    "AR": ("Arkansas Division of Emergency Management", "https://www.dps.arkansas.gov/emergency-management/adem/"),
    "CA": ("California Office of Emergency Services", "https://www.caloes.ca.gov/"),
    "CO": ("Colorado Division of Homeland Security and Emergency Management", "https://cdphe.colorado.gov/homeland-security-and-emergency-management"),
    "CT": ("Connecticut Division of Emergency Management and Homeland Security", "https://portal.ct.gov/demhs"),
    "DE": ("Delaware Emergency Management Agency", "https://dema.delaware.gov/"),
    "FL": ("Florida Division of Emergency Management", "https://www.floridadisaster.org/"),
    "GA": ("Georgia Emergency Management and Homeland Security Agency", "https://gema.georgia.gov/"),
    "HI": ("Hawaii Emergency Management Agency", "https://dod.hawaii.gov/hiema/"),
    "ID": ("Idaho Office of Emergency Management", "https://ioem.idaho.gov/"),
    "IL": ("Illinois Emergency Management Agency and Office of Homeland Security", "https://iemaohs.illinois.gov/"),
    "IN": ("Indiana Department of Homeland Security", "https://www.in.gov/dhs/"),
    "IA": ("Iowa Homeland Security and Emergency Management", "https://homelandsecurity.iowa.gov/"),
    "KS": ("Kansas Division of Emergency Management", "https://www.kansastag.gov/KDEM.asp"),
    "KY": ("Kentucky Emergency Management", "https://kyem.ky.gov/"),
    "LA": ("Louisiana Governor's Office of Homeland Security and Emergency Preparedness", "https://gohsep.la.gov/"),
    "ME": ("Maine Emergency Management Agency", "https://www.maine.gov/mema/"),
    "MD": ("Maryland Department of Emergency Management", "https://mdem.maryland.gov/"),
    "MA": ("Massachusetts Emergency Management Agency", "https://www.mass.gov/orgs/massachusetts-emergency-management-agency"),
    "MI": ("Michigan State Police Emergency Management and Homeland Security Division", "https://www.michigan.gov/msp/divisions/emhsd"),
    "MN": ("Minnesota Homeland Security and Emergency Management", "https://dps.mn.gov/divisions/hsem/"),
    "MS": ("Mississippi Emergency Management Agency", "https://www.msema.org/"),
    "MO": ("Missouri State Emergency Management Agency", "https://sema.dps.mo.gov/"),
    "MT": ("Montana Disaster and Emergency Services", "https://des.mt.gov/"),
    "NE": ("Nebraska Emergency Management Agency", "https://nema.nebraska.gov/"),
    "NV": ("Nevada Division of Emergency Management", "https://dem.nv.gov/"),
    "NH": ("New Hampshire Homeland Security and Emergency Management", "https://www.nh.gov/safety/divisions/hsem/"),
    "NJ": ("New Jersey Office of Emergency Management", "https://www.nj.gov/njoem/"),
    "NM": ("New Mexico Department of Homeland Security and Emergency Management", "https://www.dhsem.nm.gov/"),
    "NY": ("New York State Division of Homeland Security and Emergency Services", "https://www.dhses.ny.gov/"),
    "NC": ("North Carolina Emergency Management", "https://www.ncdps.gov/our-organization/emergency-management"),
    "ND": ("North Dakota Department of Emergency Services", "https://www.des.nd.gov/"),
    "OH": ("Ohio Emergency Management Agency", "https://ema.ohio.gov/"),
    "OK": ("Oklahoma Department of Emergency Management", "https://oklahoma.gov/oem.html"),
    "OR": ("Oregon Department of Emergency Management", "https://www.oregon.gov/oem/"),
    "PA": ("Pennsylvania Emergency Management Agency", "https://www.pema.pa.gov/"),
    "RI": ("Rhode Island Emergency Management Agency", "https://riema.ri.gov/"),
    "SC": ("South Carolina Emergency Management Division", "https://www.scemd.org/"),
    "SD": ("South Dakota Office of Emergency Management", "https://dps.sd.gov/emergency-services/emergency-management"),
    "TN": ("Tennessee Emergency Management Agency", "https://www.tn.gov/tema.html"),
    "TX": ("Texas Division of Emergency Management", "https://www.tdem.texas.gov/"),
    "UT": ("Utah Division of Emergency Management", "https://dem.utah.gov/"),
    "VT": ("Vermont Emergency Management", "https://vem.vermont.gov/"),
    "VA": ("Virginia Department of Emergency Management", "https://www.vaemergency.gov/"),
    "WA": ("Washington Emergency Management Division", "https://mil.wa.gov/emergency-management-division"),
    "WV": ("West Virginia Emergency Management Division", "https://emd.wv.gov/"),
    "WI": ("Wisconsin Emergency Management", "https://wem.wi.gov/"),
    "WY": ("Wyoming Office of Homeland Security", "https://hls.wyo.gov/"),
}

COMMON_STATE_CATEGORIES = {
    "insurance support": {
        "name_suffix": "Insurance Department Resources",
        "url": "https://content.naic.org/state-insurance-departments",
        "description_template": "Official insurance department directory and insurance complaint pathway for {state_name}.",
        "tags": ["insurance", "claims"],
        "required_information": ["insurer name", "claim number if available", "property address"],
        "required_documents": ["insurance policy", "damage photos", "repair estimates if available"],
    },
    "food and benefits": {
        "name_suffix": "Food and Benefits Directory",
        "url": "https://www.fns.usda.gov/snap/state-directory",
        "description_template": "Official SNAP and state food assistance directory page for {state_name}.",
        "tags": ["food", "benefits", "income disruption"],
        "required_information": ["household size", "income disruption", "address or ZIP code"],
        "required_documents": ["government ID if available", "proof of address", "income information if available"],
    },
    "local referrals": {
        "name_suffix": "Local Help Finder",
        "url": "https://www.211.org/about-us/your-local-211",
        "description_template": "Local 211 and community referral entry point for {state_name}.",
        "tags": ["food", "shelter", "county services"],
        "required_information": ["ZIP code", "immediate needs", "household size"],
        "required_documents": [],
    },
    "shelter support": {
        "name_suffix": "Shelter Finder",
        "url": "https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html",
        "description_template": "Open shelter and emergency lodging finder that may be relevant in {state_name}.",
        "tags": ["shelter", "emergency"],
        "required_information": ["current location", "household size", "medical or accessibility needs"],
        "required_documents": ["photo ID if available"],
    },
}

CALIFORNIA_EXTRAS = [
    {
        "name": "Listos California",
        "category": "preparedness and recovery",
        "url": "https://www.listoscalifornia.org/",
        "description": "California disaster readiness and multilingual community guidance.",
        "disaster_types": ["wildfire", "earthquake"],
        "counties": [],
        "tags": ["preparedness", "multilingual", "community"],
        "required_information": ["preferred language", "county", "disaster concerns"],
        "required_documents": [],
    },
    {
        "name": "CalFresh",
        "category": "food support",
        "url": "https://www.getcalfresh.org/",
        "description": "Food assistance application support for California residents.",
        "disaster_types": ["wildfire", "earthquake"],
        "counties": [],
        "tags": ["food", "benefits", "income disruption"],
        "required_information": ["household size", "income estimate", "address", "citizenship or eligibility details as required"],
        "required_documents": ["ID if available", "income information", "rent or utility information if available"],
    },
    {
        "name": "California Wildfire and Smoke Information",
        "category": "wildfire safety",
        "url": "https://www.fire.ca.gov/",
        "description": "CAL FIRE information about incidents, preparedness, and wildfire response.",
        "disaster_types": ["wildfire"],
        "counties": [],
        "tags": ["fire", "evacuation", "smoke"],
        "required_information": ["county", "incident area", "evacuation status"],
        "required_documents": [],
    },
    {
        "name": "Earthquake Warning California",
        "category": "earthquake safety",
        "url": "https://earthquake.ca.gov/",
        "description": "California earthquake safety, alerts, and recovery guidance.",
        "disaster_types": ["earthquake"],
        "counties": [],
        "tags": ["earthquake", "aftershocks", "safety"],
        "required_information": ["county", "damage type", "current safety status"],
        "required_documents": [],
    },
    {
        "name": "California Veterinary Medical Reserve Corps",
        "category": "animal support",
        "url": "https://www.calvoad.org/",
        "description": "Community support coordination that can help identify animal and evacuation resources.",
        "disaster_types": ["wildfire", "earthquake"],
        "counties": [],
        "tags": ["pets", "evacuation", "community"],
        "required_information": ["pet type", "current location", "evacuation needs"],
        "required_documents": ["vaccination records if available", "pet medications list if applicable"],
    },
]

FEDERAL_RESOURCES = [
    {
        "name": "FEMA Disaster Assistance",
        "category": "federal aid",
        "url": "https://www.disasterassistance.gov/",
        "description": "Apply for federal disaster assistance when a county has a declared disaster.",
        "state_code": "US",
        "disaster_types": ["wildfire", "earthquake"],
        "counties": [],
        "tags": ["housing", "federal", "cash assistance"],
        "required_information": ["disaster address", "current contact info", "insurance status", "household members"],
        "required_documents": ["government ID", "proof of occupancy or ownership", "insurance policy details", "damage photos"],
    },
    {
        "name": "Federal Emergency Management Agency",
        "category": "federal aid",
        "url": "https://www.fema.gov/",
        "description": "Official FEMA disaster preparedness, response, and recovery information.",
        "state_code": "US",
        "disaster_types": ["wildfire", "earthquake"],
        "counties": [],
        "tags": ["federal", "preparedness", "recovery"],
        "required_information": ["ZIP code", "disaster type", "household needs"],
        "required_documents": ["government ID if available", "proof of address if available"],
    },
    {
        "name": "SBA Disaster Assistance",
        "category": "federal aid",
        "url": "https://www.sba.gov/funding-programs/disaster-assistance",
        "description": "Federal disaster loan information for homeowners, renters, nonprofits, and businesses.",
        "state_code": "US",
        "disaster_types": ["wildfire", "earthquake"],
        "counties": [],
        "tags": ["federal", "loans", "business", "housing"],
        "required_information": ["disaster location", "applicant type", "damage details"],
        "required_documents": ["government ID", "financial information if available", "damage estimates if available"],
    },
    {
        "name": "USAGov Disaster Housing and Shelter",
        "category": "federal aid",
        "url": "https://www.usa.gov/disaster-housing-shelter",
        "description": "Federal guidance on shelters, temporary housing, and housing assistance after a disaster.",
        "state_code": "US",
        "disaster_types": ["wildfire", "earthquake"],
        "counties": [],
        "tags": ["federal", "housing", "shelter"],
        "required_information": ["ZIP code", "housing need", "FEMA registration status if available"],
        "required_documents": ["government ID if available", "FEMA registration number if available"],
    },
]


def common_state_entries(state_code: str, state_name: str) -> list[dict]:
    agency_name, agency_url = STATE_EMERGENCY_AGENCY_LINKS[state_code]
    entries = [
        {
            "name": agency_name,
            "category": "state emergency coordination",
            "url": agency_url,
            "description": f"Official {state_name} emergency management agency and disaster coordination page.",
            "state_code": state_code,
            "disaster_types": ["wildfire", "earthquake"],
            "counties": [],
            "tags": ["alerts", "statewide", "recovery"],
            "required_information": ["ZIP code", "county", "disaster type", "current safety status"],
            "required_documents": ["government ID if available", "proof of address if available"],
        }
    ]
    for category, template in COMMON_STATE_CATEGORIES.items():
        entries.append(
            {
                "name": f"{state_name} {template['name_suffix']}",
                "category": category,
                "url": template["url"],
                "description": template["description_template"].format(state_name=state_name),
                "state_code": state_code,
                "disaster_types": ["wildfire", "earthquake"],
                "counties": [],
                "tags": template["tags"],
                "required_information": template["required_information"],
                "required_documents": template["required_documents"],
            }
        )
    return entries


def main() -> None:
    STATES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for state_code, state_name in STATE_NAMES.items():
        entries = common_state_entries(state_code, state_name)
        if state_code == "CA":
            entries.extend(CALIFORNIA_EXTRAS)
        path = STATES_DIR / f"{state_code.lower()}.json"
        path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")

    (DATA_DIR / "federal_resources.json").write_text(
        json.dumps(FEDERAL_RESOURCES, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
