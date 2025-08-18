# Error Handling Improvements

This document summarizes the comprehensive error handling improvements made to the taxdumpy package.

## Overview

The error handling system has been completely redesigned to provide:
- 🚀 **User-friendly error messages** with actionable suggestions
- 🔍 **Detailed error context** and debugging information
- 🛡️ **Robust input validation** throughout the codebase
- 📋 **Comprehensive error classification** with specific exception types
- 🧪 **Extensive test coverage** for error scenarios

## Enhanced Exception Classes

### Base Exception Hierarchy

```
TaxdumpyError (base)
├── TaxDbError
│   ├── TaxdumpFileError
│   └── DatabaseCorruptionError
├── TaxidError
├── TaxRankError
└── ValidationError
```

### Exception Features

**All exceptions now include:**
- Descriptive error messages
- Contextual information (file names, line numbers, etc.)
- Actionable suggestions for resolution
- Proper inheritance for catch-all handling

### Example Error Messages

**Before:**
```
TaxidError: 99999 is not a valid taxonomy identifier
```

**After:**
```
❌ TaxID Error: TaxID 99999 is not found in the database
Suggestion: Try nearby taxids: 99995, 99996, 99997, or use search function to find organisms
```

## Input Validation

### TaxDb Class Validation

**Constructor Parameters:**
- ✅ `taxdump_dir`: Must be existing directory
- ✅ `fast`: Must be boolean
- ✅ Path resolution and permission checks

**get_node() Method:**
- ✅ Accepts both `int` and `str` taxids
- ✅ Validates positive integers
- ✅ Provides helpful suggestions for invalid taxids
- ✅ Handles legacy/merged taxids gracefully

### Search Function Validation

**_rapid_fuzz() Method:**
- ✅ Query must be non-empty string
- ✅ Limit must be positive integer ≤ 1000
- ✅ Graceful handling of empty queries
- ✅ Automatic limiting of excessive search limits

## File I/O Robustness

### Enhanced File Reading

**All taxdump file parsers now handle:**
- 🔧 **Encoding issues**: UTF-8 with replacement fallback
- 🔧 **Malformed lines**: Log warnings and continue parsing
- 🔧 **Missing files**: Clear error messages with download instructions
- 🔧 **Corrupted files**: Detection and helpful recovery suggestions
- 🔧 **Empty files**: Proper error reporting
- 🔧 **Permission errors**: Clear messages about file access

### Robust Parsing

**Each parser method (`_import_*`) includes:**
- Line-by-line error handling
- Detailed logging of parsing issues
- Continuation on non-critical errors
- Comprehensive error reporting

## CLI Error Handling

### User-Friendly Interface

**New CLI features:**
- 📱 **Emoji indicators**: Visual error classification
- 💡 **Helpful suggestions**: Actionable next steps
- 🎯 **Context-aware messages**: Specific guidance per error type
- 📊 **Progress indicators**: Clear status during operations

### Error Handler Function

```python
def handle_error(error: Exception, exit_code: int = 1) -> int:
    """Handle and display errors in a user-friendly way."""
```

**Handles all error types:**
- `ValidationError`: Input validation failures
- `TaxdumpFileError`: File-related issues
- `TaxidError`: Taxonomy ID problems
- `DatabaseCorruptionError`: Database integrity issues
- `FileNotFoundError`: Missing files
- `PermissionError`: Access issues
- `MemoryError`: Memory constraints
- `KeyboardInterrupt`: User cancellation
- Unexpected errors with bug reporting guidance

### Enhanced Argument Parser

**Improvements:**
- Better help messages with examples
- Input validation for all parameters
- Verbose mode for debugging
- Clear error messages for missing arguments

## Logging Integration

### Structured Logging

**Logging levels:**
- `DEBUG`: Detailed operation information
- `INFO`: Important status updates
- `WARNING`: Non-critical issues (malformed lines, etc.)
- `ERROR`: Serious problems requiring attention

### CLI Logging

```bash
# Enable verbose output
taxdumpy --verbose search "human"
taxdumpy -v lineage 9606
```

## Testing Coverage

### Comprehensive Test Suite

**Error handling tests cover:**
- ✅ **Exception classes**: All custom exceptions
- ✅ **Input validation**: Invalid parameters and edge cases
- ✅ **File handling**: Corrupted, missing, and permission issues
- ✅ **CLI error handling**: User-facing error messages
- ✅ **Robust parsing**: Malformed data handling
- ✅ **Edge cases**: Unicode errors, empty files, etc.

### Test Categories

1. **Unit Tests**: Individual component error handling
2. **Integration Tests**: Error propagation through system
3. **CLI Tests**: Command-line error scenarios
4. **File I/O Tests**: Filesystem error conditions
5. **Validation Tests**: Input parameter checking

## Usage Examples

### Handling Common Errors

**Invalid TaxID:**
```bash
$ taxdumpy lineage 999999999
❌ TaxID Error: TaxID 999999999 is not found in the database
Suggestion: Try nearby taxids: 999999000, 999999001, 999999002, or use search function to find organisms
```

**Missing Files:**
```bash
$ taxdumpy cache -d /nonexistent
❌ File Error: Problem with taxdump file 'nodes.dmp, names.dmp, merged.dmp, delnodes.dmp, division.dmp': Files not found
Details: Download NCBI taxdump files from ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz
```

**Invalid Search:**
```bash
$ taxdumpy search ""
❌ Input Error: Invalid value for 'query':  (expected: string)
```

### Programmatic Error Handling

```python
from taxdumpy import TaxDb, TaxidError, ValidationError

try:
    taxdb = TaxDb("/path/to/taxdump")
    node = taxdb.get_node("invalid_taxid")
except ValidationError as e:
    print(f"Input validation failed: {e}")
except TaxidError as e:
    print(f"TaxID issue: {e}")
    # e.suggestion contains helpful guidance
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Migration Guide

### For Users

**No breaking changes** - all existing functionality works the same, but with better error messages.

**New features to utilize:**
- Use `--verbose` flag for debugging
- Check error messages for helpful suggestions
- Report unexpected errors using provided GitHub links

### For Developers

**Exception handling updates:**
```python
# Old way (still works)
try:
    taxon = Taxon(taxid, taxdb)
except TaxidError:
    pass

# New way (recommended)
try:
    taxon = Taxon(taxid, taxdb)
except TaxidError as e:
    logging.warning(f"TaxID lookup failed: {e}")
    if e.suggestion:
        print(f"💡 {e.suggestion}")
```

## Performance Impact

**Minimal overhead:**
- ✅ Validation checks are lightweight
- ✅ Error handling only activates on failures
- ✅ Logging can be disabled for production
- ✅ No impact on happy path performance

## Future Enhancements

**Potential improvements:**
- 🔮 **Error recovery**: Automatic retry mechanisms
- 🔮 **Smart suggestions**: ML-based taxid recommendations
- 🔮 **Progress recovery**: Resume interrupted operations
- 🔮 **Error analytics**: Aggregate error reporting for debugging

## Testing Error Handling

```bash
# Run all error handling tests
pytest tests/test_error_handling.py -v

# Test specific error scenarios
pytest tests/test_error_handling.py::TestTaxDbValidation -v
pytest tests/test_error_handling.py::TestCLIErrorHandling -v

# Test with coverage
pytest tests/test_error_handling.py --cov=taxdumpy --cov-report=html
```

The comprehensive error handling system makes taxdumpy more robust, user-friendly, and maintainable while providing clear guidance for both users and developers when issues arise.