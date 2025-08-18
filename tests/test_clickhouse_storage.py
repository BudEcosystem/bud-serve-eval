"""Test suite for ClickHouse storage operations."""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

# Test both import paths to ensure they work
try:
    from budeval.evals.storage.clickhouse import ClickHouseStorage
    CLICKHOUSE_AVAILABLE = True
except ImportError:
    CLICKHOUSE_AVAILABLE = False
    ClickHouseStorage = None

from budeval.evals.storage.factory import get_storage_adapter, get_storage_info, health_check_storage


@pytest.mark.skipif(not CLICKHOUSE_AVAILABLE, reason="ClickHouse dependencies not available")
class TestClickHouseStorage:
    """Test ClickHouse storage adapter functionality."""

    @pytest.fixture
    def mock_clickhouse_config(self):
        """Mock ClickHouse configuration."""
        return {
            'clickhouse_host': 'localhost',
            'clickhouse_port': 9000,
            'clickhouse_database': 'budeval_test',
            'clickhouse_user': 'default',
            'clickhouse_password': '',
            'clickhouse_batch_size': 100,
            'clickhouse_pool_min_size': 1,
            'clickhouse_pool_max_size': 2,
            'clickhouse_async_insert': True,
            'clickhouse_compression': 'zstd'
        }

    @pytest.fixture
    def sample_results(self):
        """Sample evaluation results for testing."""
        return {
            'job_id': 'test-job-123',
            'model_name': 'test-model',
            'engine': 'opencompass',
            'extracted_at': datetime.now().isoformat(),
            'summary': {
                'overall_accuracy': 75.5,
                'total_datasets': 1,
                'total_examples': 100,
                'total_correct': 75,
                'model_name': 'test-model'
            },
            'datasets': [
                {
                    'dataset_name': 'test_dataset',
                    'accuracy': 75.5,
                    'total_examples': 100,
                    'correct_examples': 75,
                    'metadata': {'version': '1.0'},
                    'predictions': [
                        {
                            'example_abbr': '0',
                            'pred': ['42'],
                            'answer': ['42'],
                            'correct': [True],
                            'origin_prompt': 'What is 6 * 7?',
                            'prediction': 'The answer is 42.'
                        },
                        {
                            'example_abbr': '1',
                            'pred': ['10'],
                            'answer': ['12'],
                            'correct': [False],
                            'origin_prompt': 'What is 3 * 4?',
                            'prediction': 'The answer is 10.'
                        }
                    ]
                }
            ]
        }

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    @patch('budeval.evals.storage.clickhouse.Pool')
    def test_initialization(self, mock_pool, mock_settings, mock_clickhouse_config):
        """Test ClickHouse storage initialization."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        assert storage._pool is None
        assert storage._config == mock_settings

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    @patch('budeval.evals.storage.clickhouse.Pool')
    async def test_initialize_connection_pool(self, mock_pool_class, mock_settings, mock_clickhouse_config):
        """Test connection pool initialization."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        # Mock pool instance
        mock_pool = AsyncMock()
        mock_pool_class.return_value = mock_pool
        
        storage = ClickHouseStorage()
        await storage.initialize()
        
        # Verify pool was created with correct parameters
        mock_pool_class.assert_called_once()
        call_kwargs = mock_pool_class.call_args[1]
        assert call_kwargs['host'] == 'localhost'
        assert call_kwargs['port'] == 9000
        assert call_kwargs['database'] == 'budeval_test'
        assert call_kwargs['minsize'] == 1
        assert call_kwargs['maxsize'] == 2
        
        # Verify server settings
        server_settings = call_kwargs['server_settings']
        assert server_settings['async_insert'] == 1
        assert server_settings['wait_for_async_insert'] == 1

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    async def test_health_check_success(self, mock_settings, mock_clickhouse_config):
        """Test successful health check."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        
        # Mock connection and execution
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        
        with patch.object(storage, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            
            result = await storage.health_check()
            
            assert result is True
            mock_conn.execute.assert_called_once_with("SELECT 1")

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    async def test_health_check_failure(self, mock_settings, mock_clickhouse_config):
        """Test health check failure."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        
        # Mock connection failure
        with patch.object(storage, 'get_connection') as mock_get_conn:
            mock_get_conn.side_effect = Exception("Connection failed")
            
            result = await storage.health_check()
            
            assert result is False

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    async def test_save_results(self, mock_settings, mock_clickhouse_config, sample_results):
        """Test saving evaluation results."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        
        # Mock connection and methods
        mock_conn = AsyncMock()
        
        with patch.object(storage, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            
            # Mock the internal save methods
            with patch.object(storage, '_save_evaluation_job') as mock_save_job, \
                 patch.object(storage, '_save_dataset_results') as mock_save_datasets, \
                 patch.object(storage, '_save_predictions_batch') as mock_save_predictions:
                
                result = await storage.save_results("test-job-123", sample_results)
                
                assert result is True
                mock_save_job.assert_called_once()
                mock_save_datasets.assert_called_once()
                mock_save_predictions.assert_called_once()

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    async def test_get_results(self, mock_settings, mock_clickhouse_config):
        """Test retrieving evaluation results."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        
        # Mock connection and cursor
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (
            'test-job-123', 'test-model', 'opencompass', 
            datetime.now(), datetime.now(), 100.0,  # job times and duration
            75.5, 1, 100, 75,  # accuracy metrics
            datetime.now(), datetime.now(), datetime.now()  # timestamps
        )
        mock_cursor.fetchall.return_value = [
            ('test_dataset', 75.5, 100, 75, '{"version": "1.0"}')
        ]
        
        mock_conn = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        
        with patch.object(storage, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            
            result = await storage.get_results("test-job-123")
            
            assert result is not None
            assert result['job_id'] == 'test-job-123'
            assert result['model_name'] == 'test-model'
            assert len(result['datasets']) == 1
            assert result['datasets'][0]['dataset_name'] == 'test_dataset'

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    async def test_get_results_not_found(self, mock_settings, mock_clickhouse_config):
        """Test retrieving non-existent results."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        
        # Mock connection and cursor returning None
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None
        
        mock_conn = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        
        with patch.object(storage, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            
            result = await storage.get_results("non-existent-job")
            
            assert result is None

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    async def test_delete_results(self, mock_settings, mock_clickhouse_config):
        """Test deleting evaluation results."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        
        # Mock connection
        mock_conn = AsyncMock()
        
        with patch.object(storage, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            
            result = await storage.delete_results("test-job-123")
            
            assert result is True
            # Should call execute 3 times (for 3 tables)
            assert mock_conn.execute.call_count == 3

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    async def test_list_results(self, mock_settings, mock_clickhouse_config):
        """Test listing all available results."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        
        # Mock cursor with job IDs
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            ('job-1',),
            ('job-2',),
            ('job-3',)
        ]
        
        mock_conn = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        
        with patch.object(storage, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            
            result = await storage.list_results()
            
            assert result == ['job-1', 'job-2', 'job-3']

    @patch('budeval.evals.storage.clickhouse.secrets_settings')
    async def test_exists(self, mock_settings, mock_clickhouse_config):
        """Test checking if results exist."""
        # Setup mock config
        for key, value in mock_clickhouse_config.items():
            setattr(mock_settings, key, value)
        
        storage = ClickHouseStorage()
        
        # Mock cursor
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (1,)  # Exists
        
        mock_conn = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        
        with patch.object(storage, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_conn
            
            result = await storage.exists("test-job-123")
            
            assert result is True

    def test_parse_datetime_string(self):
        """Test datetime parsing from string."""
        storage = ClickHouseStorage()
        
        # ISO format
        dt_str = "2024-01-15T10:30:00"
        result = storage._parse_datetime(dt_str)
        assert isinstance(result, datetime)
        
        # ISO format with Z
        dt_str = "2024-01-15T10:30:00Z"
        result = storage._parse_datetime(dt_str)
        assert isinstance(result, datetime)
        
        # Invalid format should return current time
        dt_str = "invalid-date"
        result = storage._parse_datetime(dt_str)
        assert isinstance(result, datetime)

    def test_parse_datetime_datetime_object(self):
        """Test datetime parsing from datetime object."""
        storage = ClickHouseStorage()
        
        dt = datetime.now()
        result = storage._parse_datetime(dt)
        assert result == dt

    def test_parse_datetime_none(self):
        """Test datetime parsing from None."""
        storage = ClickHouseStorage()
        
        result = storage._parse_datetime(None)
        assert isinstance(result, datetime)


class TestStorageFactory:
    """Test storage factory functionality."""

    @patch('budeval.evals.storage.factory.secrets_settings')
    def test_get_storage_adapter_filesystem(self, mock_settings):
        """Test getting filesystem storage adapter."""
        mock_settings.storage_backend = "filesystem"
        
        adapter = get_storage_adapter()
        
        from budeval.evals.storage.filesystem import FilesystemStorage
        assert isinstance(adapter, FilesystemStorage)

    @patch('budeval.evals.storage.factory.secrets_settings')
    def test_get_storage_adapter_clickhouse(self, mock_settings):
        """Test getting ClickHouse storage adapter."""
        mock_settings.storage_backend = "clickhouse"
        
        if CLICKHOUSE_AVAILABLE:
            adapter = get_storage_adapter()
            assert isinstance(adapter, ClickHouseStorage)
        else:
            with pytest.raises(ImportError):
                get_storage_adapter()

    @patch('budeval.evals.storage.factory.secrets_settings')
    def test_get_storage_adapter_invalid_backend(self, mock_settings):
        """Test getting storage adapter with invalid backend."""
        mock_settings.storage_backend = "invalid"
        
        with pytest.raises(ValueError) as exc_info:
            get_storage_adapter()
        
        assert "Unsupported storage backend: invalid" in str(exc_info.value)

    @patch('budeval.evals.storage.factory.secrets_settings')
    def test_get_storage_info_filesystem(self, mock_settings):
        """Test getting filesystem storage info."""
        mock_settings.storage_backend = "filesystem"
        
        info = get_storage_info()
        
        assert info['backend'] == 'filesystem'
        assert 'base_path' in info
        assert info['description'] == 'Local filesystem storage with JSON files'

    @patch('budeval.evals.storage.factory.secrets_settings')
    def test_get_storage_info_clickhouse(self, mock_settings):
        """Test getting ClickHouse storage info."""
        mock_settings.storage_backend = "clickhouse"
        mock_settings.clickhouse_host = "localhost"
        mock_settings.clickhouse_port = 9000
        mock_settings.clickhouse_database = "budeval"
        mock_settings.clickhouse_user = "default"
        mock_settings.clickhouse_batch_size = 1000
        mock_settings.clickhouse_async_insert = True
        
        info = get_storage_info()
        
        assert info['backend'] == 'clickhouse'
        assert info['host'] == 'localhost'
        assert info['port'] == 9000
        assert info['database'] == 'budeval'
        assert info['batch_size'] == 1000
        assert info['async_insert'] is True

    async def test_health_check_storage_with_health_check(self):
        """Test health check on storage with health_check method."""
        mock_storage = AsyncMock()
        mock_storage.health_check.return_value = True
        mock_storage.__class__.__name__ = "MockStorage"
        
        result = await health_check_storage(mock_storage)
        
        assert result['backend'] == 'MockStorage'
        assert result['healthy'] is True
        assert result['error'] is None

    async def test_health_check_storage_without_health_check(self):
        """Test health check on storage without health_check method."""
        mock_storage = AsyncMock()
        # Remove health_check method
        del mock_storage.health_check
        mock_storage.list_results.return_value = []
        mock_storage.__class__.__name__ = "MockStorage"
        
        result = await health_check_storage(mock_storage)
        
        assert result['backend'] == 'MockStorage'
        assert result['healthy'] is True
        assert result['error'] is None

    async def test_health_check_storage_failure(self):
        """Test health check failure."""
        mock_storage = AsyncMock()
        mock_storage.health_check.side_effect = Exception("Connection failed")
        mock_storage.__class__.__name__ = "MockStorage"
        
        result = await health_check_storage(mock_storage)
        
        assert result['backend'] == 'MockStorage'
        assert result['healthy'] is False
        assert result['error'] == "Connection failed"


if __name__ == "__main__":
    pytest.main([__file__])