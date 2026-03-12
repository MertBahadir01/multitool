try:
    from .ts_tool import TimestampConverterTool
except ImportError:
    from .timestamp_tool import TimestampConverterTool
TOOL_META = {"id": "timestamp_converter", "name": "Timestamp Converter", "category": "developer", "widget_class": TimestampConverterTool}
