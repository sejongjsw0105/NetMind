from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .stages import FieldSource, ParsingStage


@dataclass
class FieldMetadata:
    """각 필드 값의 메타데이터"""
    
    value: Any
    source: FieldSource
    stage: ParsingStage
    origin_file: Optional[str] = None
    origin_line: Optional[int] = None
    timestamp: Optional[float] = None  # 업데이트 시각


@dataclass
class NodeMetadata:
    """노드의 모든 필드에 대한 메타데이터"""
    
    fields: Dict[str, FieldMetadata] = field(default_factory=dict)
    
    def get(self, field_name: str, default: Any = None) -> Any:
        """필드 값 반환"""
        if field_name in self.fields:
            return self.fields[field_name].value
        return default
    
    def get_source(self, field_name: str) -> Optional[FieldSource]:
        """필드의 출처 반환"""
        if field_name in self.fields:
            return self.fields[field_name].source
        return None
    
    def set(
        self,
        field_name: str,
        value: Any,
        source: FieldSource,
        stage: ParsingStage,
        origin_file: Optional[str] = None,
        origin_line: Optional[int] = None,
    ) -> None:
        """필드 값 설정"""
        self.fields[field_name] = FieldMetadata(
            value=value,
            source=source,
            stage=stage,
            origin_file=origin_file,
            origin_line=origin_line,
        )
    
    def should_update(self, field_name: str, new_source: FieldSource) -> bool:
        """필드를 업데이트해야 하는지 판단"""
        from .stages import should_update_field
        
        current_source = self.get_source(field_name)
        return should_update_field(current_source, new_source)


@dataclass
class EdgeMetadata:
    """엣지의 모든 필드에 대한 메타데이터"""
    
    fields: Dict[str, FieldMetadata] = field(default_factory=dict)
    
    def get(self, field_name: str, default: Any = None) -> Any:
        if field_name in self.fields:
            return self.fields[field_name].value
        return default
    
    def get_source(self, field_name: str) -> Optional[FieldSource]:
        if field_name in self.fields:
            return self.fields[field_name].source
        return None
    
    def set(
        self,
        field_name: str,
        value: Any,
        source: FieldSource,
        stage: ParsingStage,
        origin_file: Optional[str] = None,
        origin_line: Optional[int] = None,
    ) -> None:
        self.fields[field_name] = FieldMetadata(
            value=value,
            source=source,
            stage=stage,
            origin_file=origin_file,
            origin_line=origin_line,
        )
    
    def should_update(self, field_name: str, new_source: FieldSource) -> bool:
        from .stages import should_update_field
        
        current_source = self.get_source(field_name)
        return should_update_field(current_source, new_source)
