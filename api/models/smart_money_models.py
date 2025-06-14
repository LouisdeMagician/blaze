"""
API models for smart money tracking.
"""
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, validator
import time


class TransactionData(BaseModel):
    """
    Model for transaction data.
    """
    tx_hash: str = Field(..., description="Transaction hash")
    from_address: str = Field(..., description="Sender address")
    to_address: str = Field(..., description="Receiver address")
    timestamp: float = Field(..., description="Transaction timestamp")
    amount: float = Field(..., description="Transaction amount")
    token_address: Optional[str] = Field(None, description="Token address")
    success: Optional[bool] = Field(True, description="Whether transaction was successful")


class HolderData(BaseModel):
    """
    Model for token holder data.
    """
    address: str = Field(..., description="Wallet address")
    amount: float = Field(..., description="Token amount")
    percentage: Optional[float] = Field(None, description="Percentage of total supply")


class SmartWalletIdentificationRequest(BaseModel):
    """
    Model for smart wallet identification request.
    """
    transactions: List[TransactionData] = Field(..., description="List of transaction data")


class SmartWalletResponse(BaseModel):
    """
    Model for a smart wallet entry.
    """
    address: str = Field(..., description="Wallet address")
    smart_score: float = Field(..., description="Smart money score")
    label: Optional[str] = Field("Unknown", description="Wallet label")
    metrics: Dict[str, Any] = Field(..., description="Wallet metrics")


class SmartWalletListResponse(BaseModel):
    """
    Model for smart wallet list response.
    """
    timestamp: float = Field(default_factory=time.time, description="Timestamp of response")
    wallets: List[SmartWalletResponse] = Field(..., description="List of smart wallets")
    count: int = Field(..., description="Number of smart wallets")


class FlowTrackingRequest(BaseModel):
    """
    Model for flow tracking request.
    """
    transactions: List[TransactionData] = Field(..., description="List of transaction data")


class SignificantFlow(BaseModel):
    """
    Model for significant flow data.
    """
    from_address: str = Field(..., description="Sender address")
    from_label: str = Field(..., description="Sender label")
    from_smart_score: float = Field(..., description="Sender smart score")
    to_address: str = Field(..., description="Receiver address")
    to_label: str = Field(..., description="Receiver label")
    to_smart_score: float = Field(..., description="Receiver smart score")
    amount: float = Field(..., description="Flow amount")
    transaction_count: int = Field(..., description="Number of transactions")


class FlowMetricsResponse(BaseModel):
    """
    Model for flow metrics response.
    """
    timestamp: float = Field(default_factory=time.time, description="Timestamp of response")
    status: Optional[str] = Field(None, description="Status (e.g., no_data)")
    message: Optional[str] = Field(None, description="Status message")
    total_volume: Optional[float] = Field(None, description="Total flow volume")
    smart_money_flow: Optional[float] = Field(None, description="Flow between smart money wallets")
    smart_money_inflow: Optional[float] = Field(None, description="Flow from non-smart to smart wallets")
    smart_money_outflow: Optional[float] = Field(None, description="Flow from smart to non-smart wallets")
    smart_money_flow_ratio: Optional[float] = Field(None, description="Ratio of smart money flow to total volume")
    smart_money_net_flow: Optional[float] = Field(None, description="Net flow to smart money wallets")
    node_metrics: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Metrics for each node")
    significant_flows: Optional[List[SignificantFlow]] = Field(None, description="Significant flows between smart wallets")


class ConcentrationRequest(BaseModel):
    """
    Model for token concentration request.
    """
    token_address: str = Field(..., description="Token address")
    holders: List[HolderData] = Field(..., description="List of token holders")


class SmartMoneyHolder(BaseModel):
    """
    Model for smart money holder.
    """
    address: str = Field(..., description="Wallet address")
    amount: float = Field(..., description="Token amount")
    percentage: float = Field(..., description="Percentage of total supply")
    smart_score: float = Field(..., description="Smart money score")
    label: str = Field(..., description="Wallet label")


class ConcentrationResponse(BaseModel):
    """
    Model for concentration response.
    """
    token_address: str = Field(..., description="Token address")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of response")
    concentration: float = Field(..., description="Smart money concentration ratio")
    weighted_concentration: float = Field(..., description="Weighted concentration ratio")
    total_held_by_smart_money: float = Field(..., description="Total amount held by smart money")
    total_supply: float = Field(..., description="Total token supply")
    smart_money_holder_count: int = Field(..., description="Number of smart money holders")
    top_smart_money_holders: List[SmartMoneyHolder] = Field(..., description="Top smart money holders")


class FollowerRequest(BaseModel):
    """
    Model for follower identification request.
    """
    wallet_address: str = Field(..., description="Smart money wallet address")
    transactions: List[TransactionData] = Field(..., description="List of transaction data")


class FollowerData(BaseModel):
    """
    Model for follower data.
    """
    address: str = Field(..., description="Follower address")
    correlation_score: float = Field(..., description="Correlation score")
    transaction_count: int = Field(..., description="Number of transactions")
    label: str = Field(..., description="Wallet label")


class FollowerResponse(BaseModel):
    """
    Model for follower response.
    """
    wallet_address: str = Field(..., description="Smart money wallet address")
    status: Optional[str] = Field(None, description="Status (e.g., not_found)")
    message: Optional[str] = Field(None, description="Status message")
    smart_score: Optional[float] = Field(None, description="Smart money score")
    label: Optional[str] = Field(None, description="Wallet label")
    follower_count: Optional[int] = Field(None, description="Number of followers")
    followers: Optional[List[FollowerData]] = Field(None, description="List of followers")


class SentimentRequest(BaseModel):
    """
    Model for sentiment request.
    """
    token_address: str = Field(..., description="Token address")
    transactions: List[TransactionData] = Field(..., description="List of transaction data")


class SentimentResponse(BaseModel):
    """
    Model for sentiment response.
    """
    token_address: str = Field(..., description="Token address")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of response")
    accumulation_score: float = Field(..., description="Accumulation/distribution score (-1 to 1)")
    buy_pressure: float = Field(..., description="Buy pressure (0 to 1)")
    sell_pressure: float = Field(..., description="Sell pressure (0 to 1)")
    consensus_score: float = Field(..., description="Consensus score (0 to 1)")
    sentiment: str = Field(..., description="Overall sentiment")
    total_smart_money_volume: float = Field(..., description="Total volume from smart money")
    active_smart_wallets: int = Field(..., description="Number of active smart wallets")


class WalletLabelRequest(BaseModel):
    """
    Model for wallet label request.
    """
    wallet_address: str = Field(..., description="Wallet address")
    label: str = Field(..., description="Descriptive label")


class WalletLabelResponse(BaseModel):
    """
    Model for wallet label response.
    """
    status: str = Field(..., description="Status (success/error)")
    wallet_address: str = Field(..., description="Wallet address")
    label: str = Field(..., description="Descriptive label") 