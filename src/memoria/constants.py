"""Default constants and thresholds for Memoria."""

# Token limits
MAX_CHUNK_TOKENS = 3000
MAX_RECALL_TOKENS = 2000

# Dedup threshold (cosine similarity)
DEDUP_THRESHOLD = 0.95

# Default decay parameters
# Exponential decay rate (higher = faster forgetting). Halbwertszeit ≈ ln(2)/λ.
DEFAULT_LAMBDA = 0.01
DEFAULT_PURGE_THRESHOLD = 0.05
DEFAULT_HARD_DELETE_THRESHOLD = 0.01
DEFAULT_HARD_DELETE_AGE_DAYS = 90

# Interaction boost values
BOOST_CREATE = 0.10
BOOST_RECALL = 0.15
BOOST_UPDATE = 0.20
BOOST_REFERENCE = 0.08
PENALTY_IGNORE = -0.02

# Retrieval defaults
DEFAULT_TOP_N = 5
MAX_TOP_N = 10
HYBRID_BM25_WEIGHT = 0.3
HYBRID_VECTOR_WEIGHT = 0.7

# API
API_PREFIX = "/api/v1"

# System namespaces
SYSTEM_NAMESPACE = "__system__"
SHARED_NAMESPACE = "shared"
