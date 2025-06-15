# Blaze Analyst - Technical Context

## Technology Stack

### Backend Infrastructure
- **Programming Language**: Python
- **Web Framework**: FastAPI / Flask
- **Runtime Storage**: 
  - In-memory caching using CacheRepo with TTLCache and LFUCache
  - Strict memory limits with size guards and eviction policies
  - Completely stateless with no database dependency

### Blockchain Integration
- **RPC Providers**: 
  - Helius (for Solana)
  - Custom RPC endpoints as backup
- **Web3 Libraries**: 
  - solana-py for Solana interaction
- **Contract Parsing**: Dynamic program parsing for Solana contracts
- **Real-time Data**: Helius WebSocket API for event streaming

### Data Processing
- **Cache Framework**: cachetools with TTLCache and LFUCache
- **Stream Processing**: WebSocket-based event processing
- **Analysis Pipeline**: Real-time analysis of blockchain data
- **Warm Loading**: Pre-population of caches on startup

### High Availability
- **Deployment Pattern**: Active-passive with Kubernetes
- **Failover Mechanism**: Sub-second failover with WebSocket sync
- **Resource Protection**: PodDisruptionBudget to ensure availability
- **Health Checks**: Liveness, readiness, and startup probes
- **Memory Protection**: Strict RAM limits with LFU eviction

### Analytics Components
- **Analysis Frameworks**: NetworkX, NumPy, Pandas
- **Statistical Analysis**: scipy, statsmodels
- **Pattern Detection**: Custom algorithms for detecting anomalies

### Telegram Integration
- **Bot Framework**: python-telegram-bot
- **Message Formatting**: Telegram Markdown V2
- **Interactive Components**: Inline keyboards, buttons

## Development Environment
- **Code Repository**: GitHub
- **CI/CD**: GitHub Actions
- **Environment Management**: Python virtual environments, Docker
- **Container Orchestration**: Kubernetes for deployment and scaling
- **Local Testing**: pytest for unit tests, Locust for load testing
- **HA Testing**: Custom smoke tests for failover verification
- **Monitoring**: Custom monitoring, Grafana, Prometheus

## Technical Constraints

### Blockchain Limitations
- **RPC Rate Limits**: Must implement backoff strategies and multiple providers
- **Block Confirmation Times**: Solana has fast but variable finality times
- **Contract Verification**: Not all programs have verified source code

### Performance Requirements
- **Scan Response Time**: < 5 seconds for basic scans
- **Analysis Delivery**: Near real-time (< 30 seconds from request)
- **Concurrency**: Support for 100+ simultaneous users with asyncio
- **Failover Time**: < 2 seconds for high availability
- **Cache Repopulation**: < 30 seconds after failover

### Memory Constraints
- **RAM Usage**: Enforce hard limits to prevent OOM conditions
- **Cache Sizes**: Configurable TTL and size limits per cache type
- **Eviction Policy**: LFU (Least Frequently Used) for memory management
- **Memory Monitoring**: Proactive warnings at 80% of limit

### Telegram Constraints
- **Message Size Limits**: 4096 characters per message
- **Rate Limiting**: Maximum of 30 messages per second
- **Media Limitations**: Formatting and embedding restrictions

### Security Requirements
- **User Data Protection**: No storage of user information
- **API Security**: Rate limiting, input validation
- **Blockchain Security**: Private key management for any on-chain operations

## External Dependencies

### Third-Party Services
- **Helius API**: For enhanced Solana data
- **Helius WebSocket**: For real-time data and warm standby sync
- **Solscan/SolanaFM**: For contract verification and transaction history
- **CoinGecko/CoinMarketCap**: For price and market data

### Data Sources
- **Blockchain Nodes**: Direct access to blockchain data
- **DEX APIs**: For liquidity and trading information
- **Token Metadata**: Various sources for token information

## Integration Points

### User-Facing Integrations
- **Telegram Bot API**: Primary user interface
- **Web Dashboard** (future): Advanced analytics and configuration

### System Integrations
- **Blockchain RPCs**: For on-chain data access
- **Exchange APIs**: For market data
- **External Analytics**: For supplementary data
- **Internal Services**: gRPC/REST endpoints between components

## Technical Debt & Challenges

### Known Challenges
- **Solana Program Complexity**: Analyzing complex program structures
- **Data Volume**: Processing high volumes of transaction data efficiently
- **Memory Management**: Optimizing memory usage for in-memory analysis
- **Computation Speed**: Ensuring quick analysis without database indexing
- **Failover Reliability**: Ensuring consistent warm standby synchronization

### Future Scalability Concerns
- **Processing Latency**: Maintaining performance as user base grows
- **Solana Network Changes**: Adapting to protocol updates
- **Memory Constraints**: Managing complex analyses within RAM limits
- **Kubernetes Management**: Ensuring proper orchestration as scale increases

## Monitoring & Observability
- **Log Management**: Centralized logging system
- **Performance Metrics**: Response times, queue depths, error rates
- **Memory Metrics**: Cache sizes, hit rates, eviction frequency
- **High Availability Metrics**: Failover times, recovery rates
- **User Metrics**: Usage patterns, command popularity

## Technical Roadmap
- **Phase 1**: Basic contract scanning and Telegram integration (Complete)
  - Includes in-memory repository, warm loading, and HA setup
- **Phase 2**: Advanced analytics and risk scoring system (Complete)
- **Phase 3**: Enhanced Solana-specific analytics (Complete)
- **Phase 4**: Real-time pattern detection and advanced analytics (Next) 