# API Consistency Improvements

This document outlines the comprehensive API consistency improvements made to the taxdumpy package to create a unified interface across different database backends.

## Overview

The API consistency improvements provide:
- 🏗️ **Abstract base class** defining common interface for all backends
- 🔄 **Standardized method signatures** across TaxDb and TaxSQLite
- 🛠️ **Factory function** for easy backend selection
- 🎯 **Consistent error handling** across all implementations
- 📋 **Type hints** for better IDE support and code clarity

## Abstract Base Class

### TaxonomyDatabase

A new abstract base class `TaxonomyDatabase` defines the common interface that all database backends must implement:

```python
from abc import ABC, abstractmethod
from taxdumpy.database import TaxonomyDatabase

class TaxonomyDatabase(ABC):
    """Abstract base class for taxonomy database backends."""
    
    @abstractmethod
    def get_node(self, taxid: Union[int, str]) -> Node:
        """Get a taxonomy node by taxid."""
        pass
    
    @abstractmethod
    def fuzzy_search(self, query: str, limit: int = 10) -> None:
        """Print fuzzy search results to console."""
        pass
    
    @abstractmethod
    def _rapid_fuzz(self, query: str, limit: int = 10) -> List[Dict[str, Union[str, int]]]:
        """Perform fuzzy search and return structured results."""
        pass
    
    # ... additional abstract methods
```

### Benefits

- **Interface guarantee**: All backends implement the same methods
- **Type safety**: Clear method signatures with type hints
- **Documentation**: Built-in method documentation
- **Extensibility**: Easy to add new backend implementations

## Standardized Method Signatures

### Before (Inconsistent)

```python
# TaxDb
def get_node(self, taxid: Union[int, str]) -> Node: ...
def fuzzy_search(self, kw: str, limit: int = 10) -> None: ...

# TaxSQLite  
def get_node(self, taxid: int) -> Node: ...              # Different type signature!
def fuzzy_search(self, kw: str, limit: int = 10): ...    # Missing return type!
```

### After (Consistent)

```python
# Both TaxDb and TaxSQLite
def get_node(self, taxid: Union[int, str]) -> Node: ...
def fuzzy_search(self, query: str, limit: int = 10) -> None: ...
def _rapid_fuzz(self, query: str, limit: int = 10) -> List[Dict[str, Union[str, int]]]: ...
```

### Standardized Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_node` | `(taxid: Union[int, str]) -> Node` | Get taxonomy node by ID |
| `fuzzy_search` | `(query: str, limit: int = 10) -> None` | Print search results |
| `_rapid_fuzz` | `(query: str, limit: int = 10) -> List[Dict]` | Return structured search results |
| `__len__` | `() -> int` | Number of nodes in database |
| `__repr__` | `() -> str` | String representation |
| `close` | `() -> None` | Close database connection |

## Factory Function

### create_database()

A new factory function provides a unified way to create database backends:

```python
from taxdumpy import create_database

# Create SQLite backend
db = create_database("/path/to/taxdump", backend="sqlite")

# Create in-memory/pickle backend
db = create_database("/path/to/taxdump", backend="dict")

# With additional parameters
db = create_database("/path/to/taxdump", backend="dict", fast=True)
```

### Supported Backends

| Backend | Aliases | Description |
|---------|---------|-------------|
| `"sqlite"` | `"sql"` | SQLite-based persistent storage |
| `"dict"` | `"memory"`, `"pickle"` | In-memory dictionary with pickle caching |

### Benefits

- **Simplified instantiation**: One function for all backends
- **Parameter validation**: Consistent error handling for invalid backends
- **Future-proof**: Easy to add new backends without breaking existing code
- **Type safety**: Returns properly typed TaxonomyDatabase instance

## Consistent Error Handling

### Unified Validation

Both backends now use identical validation logic:

```python
# Before: Different validation approaches
# TaxDb: Comprehensive validation with suggestions
# TaxSQLite: Basic validation with simple errors

# After: Identical validation across backends
@staticmethod
def _validate_taxid(taxid: Union[int, str]) -> int:
    """Validate and convert taxid to integer."""
    # Same implementation in both TaxDb and TaxSQLite
```

### Error Message Consistency

```python
# Both backends now provide identical error messages
try:
    node = db.get_node("invalid")
except TaxidError as e:
    print(e)  # Same format regardless of backend
    # "TaxID invalid is not found in the database"
    # "Suggestion: Try nearby taxids: 123, 124, 125, or use search function"
```

### Added Features to TaxSQLite

| Feature | Description |
|---------|-------------|
| Input validation | String/int taxid conversion and validation |
| Suggestion system | Similar taxid recommendations on lookup failure |
| Legacy taxid mapping | Enhanced merged taxid handling with better error messages |
| Deleted taxid detection | Proper handling of deleted taxids with helpful messages |

## Usage Examples

### Polymorphic Usage

```python
from taxdumpy import create_database, TaxonomyDatabase

def process_taxonomy(db: TaxonomyDatabase, taxid: str):
    """Works with any backend thanks to consistent interface."""
    try:
        node = db.get_node(taxid)
        print(f"Found: {node.name} ({node.rank})")
        
        # Search for related organisms
        db.fuzzy_search(node.name, limit=5)
        
    except Exception as e:
        print(f"Error: {e}")

# Use with any backend
sqlite_db = create_database("/path/to/taxdump", "sqlite")
dict_db = create_database("/path/to/taxdump", "dict")

process_taxonomy(sqlite_db, "9606")  # Works
process_taxonomy(dict_db, "9606")    # Also works
```

### Context Manager Support

```python
# Both backends support context manager protocol
with create_database("/path/to/taxdump", "sqlite") as db:
    node = db.get_node("9606")
    print(node.name)
# Database automatically closed
```

### Consistent Search Results

```python
# Both backends now return identical search result format
results = db._rapid_fuzz("escherichia", limit=5)
for result in results:
    print(f"{result['taxid']}: {result['name']} ({result['score']}%)")
```

## Backward Compatibility

### No Breaking Changes

All existing code continues to work unchanged:

```python
# Existing code still works
from taxdumpy import TaxDb, TaxSQLite

db1 = TaxDb("/path/to/taxdump")
db2 = TaxSQLite("/path/to/taxdump")

# All existing methods work as before
node = db1.get_node(9606)
db2.fuzzy_search("human")
```

### Enhanced Functionality

Existing backends now have enhanced capabilities:

- **TaxSQLite**: Added `_rapid_fuzz()` method for structured search results
- **TaxSQLite**: Added `__len__()` method for consistent length checking
- **TaxSQLite**: Enhanced `get_node()` with same validation as TaxDb

## Type Safety Improvements

### Complete Type Annotations

```python
from typing import Union, List, Dict

class TaxonomyDatabase(ABC):
    @abstractmethod
    def get_node(self, taxid: Union[int, str]) -> Node: ...
    
    @abstractmethod  
    def _rapid_fuzz(self, query: str, limit: int = 10) -> List[Dict[str, Union[str, int]]]: ...
    
    @property
    @abstractmethod
    def all_names(self) -> List[str]: ...
    
    @property
    @abstractmethod
    def name2taxid(self) -> Dict[str, int]: ...
```

### IDE Support

- **Autocomplete**: IDEs can now provide accurate method suggestions
- **Type checking**: Tools like mypy can verify type correctness
- **Documentation**: Hover tooltips show method signatures and descriptions

## Testing API Consistency

### Polymorphic Tests

```python
import pytest
from taxdumpy import create_database

@pytest.mark.parametrize("backend", ["sqlite", "dict"])
def test_get_node_consistency(backend, sample_taxdump_dir):
    """Test that both backends behave identically."""
    db = create_database(sample_taxdump_dir, backend)
    
    # Both should handle string taxids
    node1 = db.get_node("9606")
    node2 = db.get_node(9606)
    assert node1.taxid == node2.taxid
    
    # Both should raise identical errors
    with pytest.raises(TaxidError) as exc_info:
        db.get_node("999999999")
    assert "not found" in str(exc_info.value)
```

### Interface Compliance

```python
def test_interface_compliance():
    """Test that all backends implement required interface."""
    from taxdumpy.database import TaxonomyDatabase
    from taxdumpy import TaxDb, TaxSQLite
    
    assert issubclass(TaxDb, TaxonomyDatabase)
    assert issubclass(TaxSQLite, TaxonomyDatabase)
```

## Performance Considerations

### No Performance Impact

- **Interface overhead**: Minimal - abstract methods are resolved at import time
- **Validation consistency**: Same validation logic, no additional overhead
- **Factory function**: Simple instantiation wrapper with no runtime cost

### Memory Efficiency

- **Shared validation**: Both backends use identical validation methods
- **Lazy loading**: Abstract properties maintain lazy loading patterns
- **Context management**: Proper resource cleanup in both backends

## Migration Guide

### For New Code

**Recommended approach**: Use the factory function for new code:

```python
# Preferred for new code
from taxdumpy import create_database

db = create_database("/path/to/taxdump", "sqlite")
```

### For Existing Code

**No changes required**: All existing code continues to work:

```python
# Existing code works unchanged
from taxdumpy import TaxDb, TaxSQLite

db = TaxDb("/path/to/taxdump")
# All existing functionality preserved
```

### Enhanced Error Handling

Existing code can now benefit from enhanced error handling without changes:

```python
# Existing code now gets better error messages
try:
    db = TaxSQLite("/path/to/taxdump")
    node = db.get_node("invalid_taxid")
except TaxidError as e:
    print(e)  # Now includes helpful suggestions!
```

## Future Extensions

### Easy Backend Addition

The abstract base class makes it simple to add new backends:

```python
class TaxRedis(TaxonomyDatabase):
    """Redis-based taxonomy database."""
    
    def get_node(self, taxid: Union[int, str]) -> Node:
        # Implement Redis-specific logic
        pass
    
    # Implement other abstract methods...
```

### Plugin Architecture

The factory function can be extended to support plugins:

```python
# Future: Plugin registration
register_backend("redis", TaxRedis)
db = create_database("/path/to/taxdump", "redis", host="localhost")
```

## Testing the Implementation

```bash
# Test basic functionality
python -c "
from taxdumpy import create_database
db1 = create_database('/path/to/taxdump', 'sqlite')
db2 = create_database('/path/to/taxdump', 'dict')
print('✅ Factory function works')
print(f'SQLite DB: {len(db1)} nodes')
print(f'Dict DB: {len(db2)} nodes')
"

# Test interface compliance
python -c "
from taxdumpy import TaxDb, TaxSQLite, TaxonomyDatabase
assert issubclass(TaxDb, TaxonomyDatabase)
assert issubclass(TaxSQLite, TaxonomyDatabase)
print('✅ Interface compliance verified')
"

# Test consistent error handling
python -c "
from taxdumpy import create_database
from taxdumpy.basic import ValidationError

for backend in ['sqlite', 'dict']:
    db = create_database('/path/to/taxdump', backend)
    try:
        db.get_node('')
    except ValidationError:
        print(f'✅ {backend} backend has consistent validation')
"
```

## Summary

The API consistency improvements provide:

1. **🏗️ Unified Interface**: Abstract base class ensures consistent API
2. **🔄 Method Standardization**: Identical signatures across all backends
3. **🛠️ Factory Function**: Simplified backend creation and selection
4. **🎯 Error Consistency**: Uniform validation and error messages
5. **📋 Type Safety**: Complete type annotations for better development experience
6. **🔒 Backward Compatibility**: All existing code continues to work
7. **🚀 Future-Proof**: Easy to extend with new backends

These improvements make taxdumpy more maintainable, easier to use, and provide a solid foundation for future enhancements while preserving all existing functionality.