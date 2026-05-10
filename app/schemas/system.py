from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any, Dict

class SystemConfigResponse(BaseModel):
    key: str
    value: Any
    model_config = ConfigDict(from_attributes=True)

class TranslationResponse(BaseModel):
    key: str
    text: str
    model_config = ConfigDict(from_attributes=True)

class DeviceTokenCreate(BaseModel):
    token: str
    platform: str # 'ios', 'android'
