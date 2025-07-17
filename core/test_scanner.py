# type: ignore
import pytest
import asyncio
from core.scanner import MinecraftScanner, ScannerModule, ScanResult

class DummyModule(ScannerModule):
    def __init__(self):
        self.initialized = False
        self.results = []
        self.finalized = False
    async def initialize(self, scanner):
        self.initialized = True
    async def process_result(self, result: ScanResult):
        self.results.append(result)
    async def finalize(self):
        self.finalized = True

@pytest.mark.asyncio
async def test_module_registration_and_processing(tmp_path):
    scanner = MinecraftScanner()
    module = DummyModule()
    scanner.add_module(module)
    await scanner.initialize()
    assert module.initialized
    # Simulate a scan result
    result = ScanResult(ip='127.0.0.1', port=25565, success=True)
    await module.process_result(result)
    assert module.results == [result]
    await module.finalize()
    assert module.finalized 