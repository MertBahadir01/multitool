"""Discovers and loads tool plugins from the /tools directory."""

import importlib
import os
import sys


class PluginManager:
    def __init__(self):
        self.tools = {}

    def discover_tools(self, tools_dir="tools"):
        """Auto-discover all tool modules."""
        if not os.path.exists(tools_dir):
            return
        for folder in sorted(os.listdir(tools_dir)):
            folder_path = os.path.join(tools_dir, folder)
            if not os.path.isdir(folder_path):
                continue
            init_file = os.path.join(folder_path, "__init__.py")
            if not os.path.exists(init_file):
                continue
            try:
                module = importlib.import_module(f"tools.{folder}")
                if hasattr(module, "TOOL_META"):
                    meta = module.TOOL_META
                    self.tools[meta["id"]] = meta
            except Exception as e:
                print(f"[PluginManager] Failed to load {folder}: {e}")

    def get_tool(self, tool_id: str):
        return self.tools.get(tool_id)

    def get_all_tools(self):
        return self.tools


plugin_manager = PluginManager()
