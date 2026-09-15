from pydantic import BaseModel


class CollibraAsset(BaseModel):
    id: str
    name: str
    display_name: str = ""
    domain_id: str
    domain_name: str = ""
    type_name: str
    status: str = ""
    definition: str = ""
    description: str = ""
    synonyms: list[str] = []


class CollibraRelation(BaseModel):
    id: str
    source_id: str
    source_name: str
    source_domain_name: str
    target_id: str
    target_name: str
    target_domain_name: str
    type_name: str = ""


class PhysicalColumn(BaseModel):
    asset_id: str
    table_name: str
    column_name: str
    description: str = ""
