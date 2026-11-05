from dataclasses import dataclass

DATASET_URL = "https://open.toronto.ca/dataset/ttc-bus-delay-data/"
PACKAGE_URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id=ttc-bus-delay-data"
DATASET_ID = "e271cdae-8788-4980-96ce-6a5c95bc6618"


@dataclass(frozen=True)
class Resource:
    key: str
    official_id: str
    kind: str


DELAYS = Resource("ttc-bus-since-2025", "b5725365-9252-4bfe-b6f4-cda7ddf74341", "delays")
CODES = Resource("ttc-bus-codes", "874ae66c-9f6f-443f-91e0-1d37d416e0d8", "codes")
README_ID = "71bb1283-7388-4d23-aa4e-0f393a80abce"
