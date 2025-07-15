"""Tests for transformer registry functionality."""

from budeval.core.schemas import EvaluationEngine
from budeval.core.transformers.registry import TransformerRegistry
from budeval.core.transformers.opencompass_transformer import OpenCompassTransformer


def test_opencompass_transformer_instantiation():
    """Test that OpenCompassTransformer can be instantiated correctly."""
    # Test direct instantiation without parameters
    transformer1 = OpenCompassTransformer()
    assert transformer1.engine == EvaluationEngine.OPENCOMPASS
    
    # Test direct instantiation with engine parameter
    transformer2 = OpenCompassTransformer(EvaluationEngine.OPENCOMPASS)
    assert transformer2.engine == EvaluationEngine.OPENCOMPASS
    print("✅ OpenCompass transformer instantiation test passed")


def test_registry_get_transformer():
    """Test that TransformerRegistry can create transformer instances correctly."""
    # Test getting transformer through registry
    transformer = TransformerRegistry.get_transformer(EvaluationEngine.OPENCOMPASS)
    
    assert transformer is not None
    assert isinstance(transformer, OpenCompassTransformer)
    assert transformer.engine == EvaluationEngine.OPENCOMPASS
    print("✅ TransformerRegistry get_transformer test passed")


def test_registry_singleton_behavior():
    """Test that registry returns the same instance for repeated calls."""
    transformer1 = TransformerRegistry.get_transformer(EvaluationEngine.OPENCOMPASS)
    transformer2 = TransformerRegistry.get_transformer(EvaluationEngine.OPENCOMPASS)
    
    # Should be the same instance (singleton pattern)
    assert transformer1 is transformer2
    print("✅ Registry singleton behavior test passed")


def test_registry_registration_status():
    """Test that OpenCompass is properly registered."""
    assert TransformerRegistry.is_registered(EvaluationEngine.OPENCOMPASS)
    
    # Test listing engines
    engines = TransformerRegistry.list_engines()
    assert EvaluationEngine.OPENCOMPASS in engines
    print("✅ Registry registration status test passed")


def test_unregistered_engine_raises_error():
    """Test that requesting an unregistered engine raises ValueError."""
    # Create a mock engine that's not registered
    from enum import Enum
    
    class MockEngine(Enum):
        NONEXISTENT = "nonexistent"
    
    try:
        TransformerRegistry.get_transformer(MockEngine.NONEXISTENT)
        assert False, "Expected ValueError but none was raised"
    except ValueError as e:
        assert "No transformer registered for engine" in str(e)
        print("✅ Unregistered engine error test passed")


def run_all_tests():
    """Run all tests."""
    print("=== Running Transformer Registry Tests ===")
    
    try:
        test_opencompass_transformer_instantiation()
        test_registry_get_transformer()
        test_registry_singleton_behavior()
        test_registry_registration_status()
        test_unregistered_engine_raises_error()
        
        print("\n🎉 All transformer registry tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_all_tests() 