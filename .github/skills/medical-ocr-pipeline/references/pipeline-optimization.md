# Pipeline Optimization

Optimize medical OCR pipelines for accuracy, speed, and efficiency.

## Performance Optimization

### Model Optimization
```python
import torch
import onnxruntime as ort
from paddleocr import PaddleOCR

class OptimizedOCR:
    """Optimized OCR engine for medical documents."""
    
    def __init__(self, model_path: str, use_gpu: bool = True):
        self.model_path = model_path
        self.use_gpu = use_gpu
        self.session = None
        self.initialize_optimized_model()
    
    def initialize_optimized_model(self):
        """Initialize optimized OCR model."""
        try:
            # Initialize ONNX Runtime for optimized inference
            self.session = ort.InferenceSession(
                self.model_path,
                providers=['CUDAExecutionProvider'] if self.use_gpu else ['CPUExecutionProvider']
            )
            print(f"Optimized OCR model loaded from {self.model_path}")
        except Exception as e:
            print(f"Failed to load optimized model: {e}")
            # Fallback to standard PaddleOCR
            self.session = None
    
    def extract_text_optimized(self, image):
        """Extract text from image using optimized model.
        
        Args:
            image: Input image
            
        Returns:
            Extracted text
        """
        if self.session:
            # Preprocess image for ONNX model
            preprocessed = self._preprocess_for_onnx(image)
            
            # Run inference
            inputs = {self.session.get_inputs()[0].name: preprocessed}
            outputs = self.session.run(None, inputs)
            
            # Post-process outputs
            return self._postprocess_onnx_output(outputs)
        else:
            # Fallback to standard PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, use_space_char=True)
            result = ocr.ocr(image, cls=True)
            return self._extract_text_from_paddleocr_result(result)
    
    def _preprocess_for_onnx(self, image):
        """Preprocess image for ONNX model."""
        # Resize to model input size
        resized = cv2.resize(image, (self.input_size[1], self.input_size[0]))
        
        # Normalize pixel values
        normalized = resized.astype(np.float32) / 255.0
        
        # Transpose for model input
        transposed = np.transpose(normalized, (2, 0, 1))
        
        # Add batch dimension
        batched = np.expand_dims(transposed, axis=0)
        
        return batched
    
    def _postprocess_onnx_output(self, outputs):
        """Post-process ONNX model output."""
        # Extract text from model output
        # This depends on the specific model architecture
        # For now, return a placeholder
        return "Extracted text from ONNX model"
    
    def _extract_text_from_paddleocr_result(self, result):
        """Extract text from PaddleOCR result."""
        extracted_text = []
        for line in result:
            extracted_text.append(line[1][0])
        return ' '.join(extracted_text)
```

### Batch Processing
```python
class BatchProcessor:
    """Process medical documents in batches for efficiency."""
    
    def __init__(self, batch_size: int = 32, num_workers: int = 4):
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.ocr_engine = None
        self.preprocessor = None
    
    def setup_batch_processor(self, ocr_engine, preprocessor):
        """Setup batch processor with OCR engine and preprocessor.
        
        Args:
            ocr_engine: OCR engine
            preprocessor: Preprocessor
        """
        self.ocr_engine = ocr_engine
        self.preprocessor = preprocessor
    
    def process_batch(self, documents: List[Dict]) -> List[Dict]:
        """Process documents in batch.
        
        Args:
            documents: List of documents to process
            
        Returns:
            List of processed documents
        """
        results = []
        
        # Process documents in batches
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            batch_results = self._process_single_batch(batch)
            results.extend(batch_results)
        
        return results
    
    def _process_single_batch(self, batch: List[Dict]) -> List[Dict]:
        """Process a single batch of documents.
        
        Args:
            batch: Batch of documents
            
        Returns:
            Processed documents
        """
        # Preprocess all documents in batch
        preprocessed_batch = []
        for document in batch:
            preprocessed = self.preprocessor.preprocess(document['image'])
            preprocessed_batch.append(preprocessed)
        
        # Extract text from all documents in batch
        extracted_texts = self.ocr_engine.extract_text_batch(preprocessed_batch)
        
        # Process results
        results = []
        for i, document in enumerate(batch):
            result = {
                'document_id': document.get('id', f'doc_{i}'),
                'extracted_text': extracted_texts[i],
                'confidence': document.get('confidence', 0.0),
                'processing_time': document.get('processing_time', 0.0),
            }
            results.append(result)
        
        return results
    
    def process_documents_parallel(self, documents: List[Dict]) -> List[Dict]:
        """Process documents in parallel.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Processed documents
        """
        import concurrent.futures
        
        # Process documents in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = []
            for document in documents:
                future = executor.submit(self._process_single_document, document)
                futures.append(future)
            
            # Collect results
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        
        return results
    
    def _process_single_document(self, document: Dict) -> Dict:
        """Process a single document.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document
        """
        # Preprocess document
        preprocessed = self.preprocessor.preprocess(document['image'])
        
        # Extract text
        extracted_text = self.ocr_engine.extract_text(preprocessed)
        
        return {
            'document_id': document.get('id', 'unknown'),
            'extracted_text': extracted_text,
            'confidence': document.get('confidence', 0.0),
            'processing_time': document.get('processing_time', 0.0),
        }
```

### Memory Optimization
```python
class MemoryOptimizedProcessor:
    """Memory-optimized OCR processor."""
    
    def __init__(self, max_memory_mb: int = 1024):
        self.max_memory_mb = max_memory_mb
        self.ocr_engine = None
        self.preprocessor = None
        self.memory_monitor = None
    
    def setup_memory_optimized_processor(self, ocr_engine, preprocessor):
        """Setup memory-optimized processor.
        
        Args:
            ocr_engine: OCR engine
            preprocessor: Preprocessor
        """
        self.ocr_engine = ocr_engine
        self.preprocessor = preprocessor
        self.memory_monitor = self._setup_memory_monitor()
    
    def process_with_memory_management(self, documents: List[Dict]) -> List[Dict]:
        """Process documents with memory management.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Processed documents
        """
        results = []
        
        # Process documents with memory management
        for i, document in enumerate(documents):
            # Check memory usage
            if self.memory_monitor.is_memory_exceeded():
                # Clear memory
                self._clear_memory()
            
            # Process document
            result = self._process_single_document_with_memory_management(document)
            results.append(result)
            
            # Log progress
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(documents)} documents")
        
        return results
    
    def _setup_memory_monitor(self):
        """Setup memory monitor."""
        import psutil
        
        class MemoryMonitor:
            def __init__(self, max_memory_mb: int):
                self.max_memory_mb = max_memory_mb
                self.process = psutil.Process()
            
            def is_memory_exceeded(self) -> bool:
                """Check if memory usage exceeds limit."""
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                return memory_mb > self.max_memory_mb
        
        return MemoryMonitor(self.max_memory_mb)
    
    def _clear_memory(self):
        """Clear memory."""
        import gc
        gc.collect()
        
        # Clear OCR engine cache
        if hasattr(self.ocr_engine, 'clear_cache'):
            self.ocr_engine.clear_cache()
        
        # Clear preprocessor cache
        if hasattr(self.preprocessor, 'clear_cache'):
            self.preprocessor.clear_cache()
    
    def _process_single_document_with_memory_management(self, document: Dict) -> Dict:
        """Process a single document with memory management.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document
        """
        # Preprocess document
        preprocessed = self.preprocessor.preprocess(document['image'])
        
        # Extract text
        extracted_text = self.ocr_engine.extract_text(preprocessed)
        
        # Clean up temporary variables
        del preprocessed
        
        return {
            'document_id': document.get('id', 'unknown'),
            'extracted_text': extracted_text,
            'confidence': document.get('confidence', 0.0),
            'processing_time': document.get('processing_time', 0.0),
        }
```

### Caching Strategy
```python
class CachingStrategy:
    """Caching strategy for OCR results."""
    
    def __init__(self, cache_size: int = 1000):
        self.cache = {}
        self.cache_size = cache_size
        self.cache_hits = 0
        self.cache_misses = 0
    
    def get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Get cached result.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None
        """
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        else:
            self.cache_misses += 1
            return None
    
    def cache_result(self, cache_key: str, result: Dict):
        """Cache result.
        
        Args:
            cache_key: Cache key
            result: Result to cache
        """
        # Check if cache is full
        if len(self.cache) >= self.cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        # Cache result
        self.cache[cache_key] = result
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics.
        
        Returns:
            Cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            'cache_size': len(self.cache),
            'max_cache_size': self.cache_size,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
        }
    
    def clear_cache(self):
        """Clear cache."""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
```

### Pipeline Optimization
```python
class OptimizedMedicalOCRPipeline:
    """Optimized medical OCR pipeline."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.ocr_engine = None
        self.preprocessor = None
        self.validator = None
        self.batch_processor = None
        self.memory_optimized_processor = None
        self.caching_strategy = None
        self.setup_pipeline()
    
    def setup_pipeline(self):
        """Setup optimized pipeline."""
        # Setup OCR engine
        self.ocr_engine = self._setup_ocr_engine()
        
        # Setup preprocessor
        self.preprocessor = self._setup_preprocessor()
        
        # Setup validator
        self.validator = self._setup_validator()
        
        # Setup batch processor
        self.batch_processor = self._setup_batch_processor()
        
        # Setup memory optimized processor
        self.memory_optimized_processor = self._setup_memory_optimized_processor()
        
        # Setup caching strategy
        self.caching_strategy = self._setup_caching_strategy()
    
    def process_document(self, document: Dict) -> Dict:
        """Process document with optimized pipeline.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document
        """
        # Check cache
        cache_key = self._generate_cache_key(document)
        cached_result = self.caching_strategy.get_cached_result(cache_key)
        
        if cached_result:
            return cached_result
        
        # Process document
        result = self._process_document_optimized(document)
        
        # Cache result
        self.caching_strategy.cache_result(cache_key, result)
        
        return result
    
    def process_documents_batch(self, documents: List[Dict]) -> List[Dict]:
        """Process documents in batch.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Processed documents
        """
        # Process documents in batch
        results = self.batch_processor.process_batch(documents)
        
        # Cache results
        for i, document in enumerate(documents):
            cache_key = self._generate_cache_key(document)
            self.caching_strategy.cache_result(cache_key, results[i])
        
        return results
    
    def process_documents_memory_optimized(self, documents: List[Dict]) -> List[Dict]:
        """Process documents with memory optimization.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Processed documents
        """
        # Process documents with memory optimization
        results = self.memory_optimized_processor.process_with_memory_management(documents)
        
        # Cache results
        for i, document in enumerate(documents):
            cache_key = self._generate_cache_key(document)
            self.caching_strategy.cache_result(cache_key, results[i])
        
        return results
    
    def _setup_ocr_engine(self):
        """Setup OCR engine."""
        # Setup optimized OCR engine
        return OptimizedOCR(
            model_path=self.config.get('ocr_model_path', './models/optimized_ocr.onnx'),
            use_gpu=self.config.get('use_gpu', True)
        )
    
    def _setup_preprocessor(self):
        """Setup preprocessor."""
        # Setup optimized preprocessor
        return MedicalPreprocessor()
    
    def _setup_validator(self):
        """Setup validator."""
        # Setup optimized validator
        return MedicalValidator()
    
    def _setup_batch_processor(self):
        """Setup batch processor."""
        # Setup optimized batch processor
        return BatchProcessor(
            batch_size=self.config.get('batch_size', 32),
            num_workers=self.config.get('num_workers', 4)
        )
    
    def _setup_memory_optimized_processor(self):
        """Setup memory optimized processor."""
        # Setup memory optimized processor
        return MemoryOptimizedProcessor(
            max_memory_mb=self.config.get('max_memory_mb', 1024)
        )
    
    def _setup_caching_strategy(self):
        """Setup caching strategy."""
        # Setup caching strategy
        return CachingStrategy(
            cache_size=self.config.get('cache_size', 1000)
        )
    
    def _generate_cache_key(self, document: Dict) -> str:
        """Generate cache key for document.
        
        Args:
            document: Document to generate cache key for
            
        Returns:
            Cache key
        """
        # Generate cache key based on document properties
        key_parts = [
            str(document.get('id', 'unknown')),
            str(document.get('type', 'unknown')),
            str(document.get('quality', 'unknown')),
        ]
        
        return '_'.join(key_parts)
    
    def _process_document_optimized(self, document: Dict) -> Dict:
        """Process document with optimized pipeline.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document
        """
        # Preprocess document
        preprocessed = self.preprocessor.preprocess(document['image'])
        
        # Extract text
        extracted_text = self.ocr_engine.extract_text_optimized(preprocessed)
        
        # Validate text
        validation_result = self.validator.validate(extracted_text)
        
        return {
            'document_id': document.get('id', 'unknown'),
            'extracted_text': extracted_text,
            'validation_result': validation_result,
            'processing_time': document.get('processing_time', 0.0),
        }
```

## Best Practices

- **Use optimized models**: Use optimized OCR models for better performance
- **Implement batch processing**: Process documents in batches for efficiency
- **Use memory optimization**: Optimize memory usage for large datasets
- **Implement caching**: Cache results for faster processing
- **Use parallel processing**: Process documents in parallel for speed
- **Monitor performance**: Monitor pipeline performance
- **Optimize for accuracy**: Optimize for accuracy while maintaining speed
- **Use appropriate hardware**: Use appropriate hardware for processing

## Anti-patterns

- Using non-optimized models (can lead to poor performance)
- Not implementing batch processing (can lead to slow processing)
- Not using memory optimization (can lead to memory issues)
- Not implementing caching (can lead to redundant processing)
- Not using parallel processing (can lead to slow processing)
- Not monitoring performance (can lead to performance issues)
- Not optimizing for accuracy (can lead to incorrect results)
- Not using appropriate hardware (can lead to poor performance)
- Using inappropriate batch sizes (can lead to memory issues)
- Not testing optimization (can lead to performance issues)
# Pipeline Optimization

Optimize medical OCR pipelines for accuracy, speed, and efficiency.

## Performance Optimization

### Model Optimization
```python
import torch
import onnxruntime as ort
from paddleocr import PaddleOCR

class OptimizedOCR:
    """Optimized OCR engine for medical documents."""
    
    def __init__(self, model_path: str, use_gpu: bool = True):
        self.model_path = model_path
        self.use_gpu = use_gpu
        self.session = None
        self.initialize_optimized_model()
    
    def initialize_optimized_model(self):
        """Initialize optimized OCR model."""
        try:
            # Initialize ONNX Runtime for optimized inference
            self.session = ort.InferenceSession(
                self.model_path,
                providers=['CUDAExecutionProvider'] if self.use_gpu else ['CPUExecutionProvider']
            )
            print(f"Optimized OCR model loaded from {self.model_path}")
        except Exception as e:
            print(f"Failed to load optimized model: {e}")
            # Fallback to standard PaddleOCR
            self.session = None
    
    def extract_text_optimized(self, image):
        """Extract text from image using optimized model.
        
        Args:
            image: Input image
            
        Returns:
            Extracted text
        """
        if self.session:
            # Preprocess image for ONNX model
            preprocessed = self._preprocess_for_onnx(image)
            
            # Run inference
            inputs = {self.session.get_inputs()[0].name: preprocessed}
            outputs = self.session.run(None, inputs)
            
            # Post-process outputs
            return self._postprocess_onnx_output(outputs)
        else:
            # Fallback to standard PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, use_space_char=True)
            result = ocr.ocr(image, cls=True)
            return self._extract_text_from_paddleocr_result(result)
    
    def _preprocess_for_onnx(self, image):
        """Preprocess image for ONNX model."""
        # Resize to model input size
        resized = cv2.resize(image, (self.input_size[1], self.input_size[0]))
        
        # Normalize pixel values
        normalized = resized.astype(np.float32) / 255.0
        
        # Transpose for model input
        transposed = np.transpose(normalized, (2, 0, 1))
        
        # Add batch dimension
        batched = np.expand_dims(transposed, axis=0)
        
        return batched
    
    def _postprocess_onnx_output(self, outputs):
        """Post-process ONNX model output."""
        # Extract text from model output
        # This depends on the specific model architecture
        # For now, return a placeholder
        return "Extracted text from ONNX model"
    
    def _extract_text_from_paddleocr_result(self, result):
        """Extract text from PaddleOCR result."""
        extracted_text = []
        for line in result:
            extracted_text.append(line[1][0])
        return ' '.join(extracted_text)
```

### Batch Processing
```python
class BatchProcessor:
    """Process medical documents in batches for efficiency."""
    
    def __init__(self, batch_size: int = 32, num_workers: int = 4):
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.ocr_engine = None
        self.preprocessor = None
    
    def setup_batch_processor(self, ocr_engine, preprocessor):
        """Setup batch processor with OCR engine and preprocessor.
        
        Args:
            ocr_engine: OCR engine
            preprocessor: Preprocessor
        """
        self.ocr_engine = ocr_engine
        self.preprocessor = preprocessor
    
    def process_batch(self, documents: List[Dict]) -> List[Dict]:
        """Process documents in batch.
        
        Args:
            documents: List of documents to process
            
        Returns:
            List of processed documents
        """
        results = []
        
        # Process documents in batches
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            batch_results = self._process_single_batch(batch)
            results.extend(batch_results)
        
        return results
    
    def _process_single_batch(self, batch: List[Dict]) -> List[Dict]:
        """Process a single batch of documents.
        
        Args:
            batch: Batch of documents
            
        Returns:
            Processed documents
        """
        # Preprocess all documents in batch
        preprocessed_batch = []
        for document in batch:
            preprocessed = self.preprocessor.preprocess(document['image'])
            preprocessed_batch.append(preprocessed)
        
        # Extract text from all documents in batch
        extracted_texts = self.ocr_engine.extract_text_batch(preprocessed_batch)
        
        # Process results
        results = []
        for i, document in enumerate(batch):
            result = {
                'document_id': document.get('id', f'doc_{i}'),
                'extracted_text': extracted_texts[i],
                'confidence': document.get('confidence', 0.0),
                'processing_time': document.get('processing_time', 0.0),
            }
            results.append(result)
        
        return results
    
    def process_documents_parallel(self, documents: List[Dict]) -> List[Dict]:
        """Process documents in parallel.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Processed documents
        """
        import concurrent.futures
        
        # Process documents in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = []
            for document in documents:
                future = executor.submit(self._process_single_document, document)
                futures.append(future)
            
            # Collect results
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        
        return results
    
    def _process_single_document(self, document: Dict) -> Dict:
        """Process a single document.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document
        """
        # Preprocess document
        preprocessed = self.preprocessor.preprocess(document['image'])
        
        # Extract text
        extracted_text = self.ocr_engine.extract_text(preprocessed)
        
        return {
            'document_id': document.get('id', 'unknown'),
            'extracted_text': extracted_text,
            'confidence': document.get('confidence', 0.0),
            'processing_time': document.get('processing_time', 0.0),
        }
```

### Memory Optimization
```python
class MemoryOptimizedProcessor:
    """Memory-optimized OCR processor."""
    
    def __init__(self, max_memory_mb: int = 1024):
        self.max_memory_mb = max_memory_mb
        self.ocr_engine = None
        self.preprocessor = None
        self.memory_monitor = None
    
    def setup_memory_optimized_processor(self, ocr_engine, preprocessor):
        """Setup memory-optimized processor.
        
        Args:
            ocr_engine: OCR engine
            preprocessor: Preprocessor
        """
        self.ocr_engine = ocr_engine
        self.preprocessor = preprocessor
        self.memory_monitor = self._setup_memory_monitor()
    
    def process_with_memory_management(self, documents: List[Dict]) -> List[Dict]:
        """Process documents with memory management.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Processed documents
        """
        results = []
        
        # Process documents with memory management
        for i, document in enumerate(documents):
            # Check memory usage
            if self.memory_monitor.is_memory_exceeded():
                # Clear memory
                self._clear_memory()
            
            # Process document
            result = self._process_single_document_with_memory_management(document)
            results.append(result)
            
            # Log progress
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(documents)} documents")
        
        return results
    
    def _setup_memory_monitor(self):
        """Setup memory monitor."""
        import psutil
        
        class MemoryMonitor:
            def __init__(self, max_memory_mb: int):
                self.max_memory_mb = max_memory_mb
                self.process = psutil.Process()
            
            def is_memory_exceeded(self) -> bool:
                """Check if memory usage exceeds limit."""
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                return memory_mb > self.max_memory_mb
        
        return MemoryMonitor(self.max_memory_mb)
    
    def _clear_memory(self):
        """Clear memory."""
        import gc
        gc.collect()
        
        # Clear OCR engine cache
        if hasattr(self.ocr_engine, 'clear_cache'):
            self.ocr_engine.clear_cache()
        
        # Clear preprocessor cache
        if hasattr(self.preprocessor, 'clear_cache'):
            self.preprocessor.clear_cache()
    
    def _process_single_document_with_memory_management(self, document: Dict) -> Dict:
        """Process a single document with memory management.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document
        """
        # Preprocess document
        preprocessed = self.preprocessor.preprocess(document['image'])
        
        # Extract text
        extracted_text = self.ocr_engine.extract_text(preprocessed)
        
        # Clean up temporary variables
        del preprocessed
        
        return {
            'document_id': document.get('id', 'unknown'),
            'extracted_text': extracted_text,
            'confidence': document.get('confidence', 0.0),
            'processing_time': document.get('processing_time', 0.0),
        }
```

### Caching Strategy
```python
class CachingStrategy:
    """Caching strategy for OCR results."""
    
    def __init__(self, cache_size: int = 1000):
        self.cache = {}
        self.cache_size = cache_size
        self.cache_hits = 0
        self.cache_misses = 0
    
    def get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Get cached result.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None
        """
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        else:
            self.cache_misses += 1
            return None
    
    def cache_result(self, cache_key: str, result: Dict):
        """Cache result.
        
        Args:
            cache_key: Cache key
            result: Result to cache
        """
        # Check if cache is full
        if len(self.cache) >= self.cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        # Cache result
        self.cache[cache_key] = result
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics.
        
        Returns:
            Cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            'cache_size': len(self.cache),
            'max_cache_size': self.cache_size,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
        }
    
    def clear_cache(self):
        """Clear cache."""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
```

### Pipeline Optimization
```python
class OptimizedMedicalOCRPipeline:
    """Optimized medical OCR pipeline."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.ocr_engine = None
        self.preprocessor = None
        self.validator = None
        self.batch_processor = None
        self.memory_optimized_processor = None
        self.caching_strategy = None
        self.setup_pipeline()
    
    def setup_pipeline(self):
        """Setup optimized pipeline."""
        # Setup OCR engine
        self.ocr_engine = self._setup_ocr_engine()
        
        # Setup preprocessor
        self.preprocessor = self._setup_preprocessor()
        
        # Setup validator
        self.validator = self._setup_validator()
        
        # Setup batch processor
        self.batch_processor = self._setup_batch_processor()
        
        # Setup memory optimized processor
        self.memory_optimized_processor = self._setup_memory_optimized_processor()
        
        # Setup caching strategy
        self.caching_strategy = self._setup_caching_strategy()
    
    def process_document(self, document: Dict) -> Dict:
        """Process document with optimized pipeline.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document
        """
        # Check cache
        cache_key = self._generate_cache_key(document)
        cached_result = self.caching_strategy.get_cached_result(cache_key)
        
        if cached_result:
            return cached_result
        
        # Process document
        result = self._process_document_optimized(document)
        
        # Cache result
        self.caching_strategy.cache_result(cache_key, result)
        
        return result
    
    def process_documents_batch(self, documents: List[Dict]) -> List[Dict]:
        """Process documents in batch.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Processed documents
        """
        # Process documents in batch
        results = self.batch_processor.process_batch(documents)
        
        # Cache results
        for i, document in enumerate(documents):
            cache_key = self._generate_cache_key(document)
            self.caching_strategy.cache_result(cache_key, results[i])
        
        return results
    
    def process_documents_memory_optimized(self, documents: List[Dict]) -> List[Dict]:
        """Process documents with memory optimization.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Processed documents
        """
        # Process documents with memory optimization
        results = self.memory_optimized_processor.process_with_memory_management(documents)
        
        # Cache results
        for i, document in enumerate(documents):
            cache_key = self._generate_cache_key(document)
            self.caching_strategy.cache_result(cache_key, results[i])
        
        return results
    
    def _setup_ocr_engine(self):
        """Setup OCR engine."""
        # Setup optimized OCR engine
        return OptimizedOCR(
            model_path=self.config.get('ocr_model_path', './models/optimized_ocr.onnx'),
            use_gpu=self.config.get('use_gpu', True)
        )
    
    def _setup_preprocessor(self):
        """Setup preprocessor."""
        # Setup optimized preprocessor
        return MedicalPreprocessor()
    
    def _setup_validator(self):
        """Setup validator."""
        # Setup optimized validator
        return MedicalValidator()
    
    def _setup_batch_processor(self):
        """Setup batch processor."""
        # Setup optimized batch processor
        return BatchProcessor(
            batch_size=self.config.get('batch_size', 32),
            num_workers=self.config.get('num_workers', 4)
        )
    
    def _setup_memory_optimized_processor(self):
        """Setup memory optimized processor."""
        # Setup memory optimized processor
        return MemoryOptimizedProcessor(
            max_memory_mb=self.config.get('max_memory_mb', 1024)
        )
    
    def _setup_caching_strategy(self):
        """Setup caching strategy."""
        # Setup caching strategy
        return CachingStrategy(
            cache_size=self.config.get('cache_size', 1000)
        )
    
    def _generate_cache_key(self, document: Dict) -> str:
        """Generate cache key for document.
        
        Args:
            document: Document to generate cache key for
            
        Returns:
            Cache key
        """
        # Generate cache key based on document properties
        key_parts = [
            str(document.get('id', 'unknown')),
            str(document.get('type', 'unknown')),
            str(document.get('quality', 'unknown')),
        ]
        
        return '_'.join(key_parts)
    
    def _process_document_optimized(self, document: Dict) -> Dict:
        """Process document with optimized pipeline.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document
        """
        # Preprocess document
        preprocessed = self.preprocessor.preprocess(document['image'])
        
        # Extract text
        extracted_text = self.ocr_engine.extract_text_optimized(preprocessed)
        
        # Validate text
        validation_result = self.validator.validate(extracted_text)
        
        return {
            'document_id': document.get('id', 'unknown'),
            'extracted_text': extracted_text,
            'validation_result': validation_result,
            'processing_time': document.get('processing_time', 0.0),
        }
```

## Best Practices

- **Use optimized models**: Use optimized OCR models for better performance
- **Implement batch processing**: Process documents in batches for efficiency
- **Use memory optimization**: Optimize memory usage for large datasets
- **Implement caching**: Cache results for faster processing
- **Use parallel processing**: Process documents in parallel for speed
- **Monitor performance**: Monitor pipeline performance
- **Optimize for accuracy**: Optimize for accuracy while maintaining speed
- **Use appropriate hardware**: Use appropriate hardware for processing

## Anti-patterns

- Using non-optimized models (can lead to poor performance)
- Not implementing batch processing (can lead to slow processing)
- Not using memory optimization (can lead to memory issues)
- Not implementing caching (can lead to redundant processing)
- Not using parallel processing (can lead to slow processing)
- Not monitoring performance (can lead to performance issues)
- Not optimizing for accuracy (can lead to incorrect results)
- Not using appropriate hardware (can lead to poor performance)
- Using inappropriate batch sizes (can lead to memory issues)
- Not testing optimization (can lead to performance issues)
