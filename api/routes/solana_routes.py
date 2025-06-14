"""
Solana API routes.
Provides endpoints for Solana blockchain analysis.
"""
import io
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.services.solana_program_analyzer_service import SolanaProgramAnalyzerService, get_solana_program_analyzer_service
from src.utils.validators import validate_solana_address

router = APIRouter(prefix="/solana", tags=["solana"])
logger = logging.getLogger(__name__)

@router.get("/program/{program_id}")
async def analyze_program(program_id: str, analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)):
    """
    Analyze a Solana program.
    
    Args:
        program_id: The program ID to analyze
        
    Returns:
        Analysis results
    """
    if not validate_solana_address(program_id):
        raise HTTPException(status_code=400, detail="Invalid Solana address format")
    
    result = await analyzer.analyze_program(program_id)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
    
    return result

@router.get("/token/{token_address}")
async def analyze_token(token_address: str, analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)):
    """
    Analyze a token.
    
    Args:
        token_address: The token address to analyze
        
    Returns:
        Analysis results
    """
    if not validate_solana_address(token_address):
        raise HTTPException(status_code=400, detail="Invalid Solana address format")
    
    result = analyzer.analyze_token(token_address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
    
    return result

@router.get("/nft/{nft_address}")
async def analyze_nft(nft_address: str, analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)):
    """
    Analyze an NFT.
    
    Args:
        nft_address: The NFT address to analyze
        
    Returns:
        Analysis results
    """
    if not validate_solana_address(nft_address):
        raise HTTPException(status_code=400, detail="Invalid Solana address format")
    
    result = await analyzer.analyze_nft(nft_address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
    
    return result

@router.get("/visualize/program/{program_id}")
async def visualize_program_interactions(
    program_id: str, 
    title: Optional[str] = None,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Visualize interactions between a program and related accounts.
    
    Args:
        program_id: The program ID to analyze
        title: Optional custom title for the visualization
        
    Returns:
        Visualization image
    """
    if not validate_solana_address(program_id):
        raise HTTPException(status_code=400, detail="Invalid Solana address format")
    
    result = await analyzer.visualize_program_interactions(program_id, title)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Visualization failed"))
    
    # Return image as streaming response
    return StreamingResponse(
        io.BytesIO(result["visualization"].getvalue()), 
        media_type="image/png"
    )

@router.get("/visualize/token/{token_mint}")
async def visualize_token_holders(
    token_mint: str, 
    title: Optional[str] = None,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Visualize token holder relationships for a specific token.
    
    Args:
        token_mint: The token mint address
        title: Optional custom title for the visualization
        
    Returns:
        Visualization image
    """
    if not validate_solana_address(token_mint):
        raise HTTPException(status_code=400, detail="Invalid Solana address format")
    
    result = await analyzer.visualize_token_holders(token_mint, title)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Visualization failed"))
    
    # Return image as streaming response
    return StreamingResponse(
        io.BytesIO(result["visualization"].getvalue()), 
        media_type="image/png"
    )

@router.get("/visualize/account/{account_address}")
async def visualize_account_hierarchy(
    account_address: str, 
    title: Optional[str] = None,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Visualize the hierarchy of related accounts starting from a root account.
    
    Args:
        account_address: The root account address
        title: Optional custom title for the visualization
        
    Returns:
        Visualization image
    """
    if not validate_solana_address(account_address):
        raise HTTPException(status_code=400, detail="Invalid Solana address format")
    
    result = await analyzer.visualize_account_hierarchy(account_address, title)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Visualization failed"))
    
    # Return image as streaming response
    return StreamingResponse(
        io.BytesIO(result["visualization"].getvalue()), 
        media_type="image/png"
    )

@router.get("/visualize/transaction/{transaction_signature}")
async def visualize_transaction_accounts(
    transaction_signature: str, 
    title: Optional[str] = None,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Visualize the accounts involved in a specific transaction.
    
    Args:
        transaction_signature: The transaction signature
        title: Optional custom title for the visualization
        
    Returns:
        Visualization image
    """
    result = await analyzer.visualize_transaction_accounts(transaction_signature, title)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Visualization failed"))
    
    # Return image as streaming response
    return StreamingResponse(
        io.BytesIO(result["visualization"].getvalue()), 
        media_type="image/png"
    )

@router.post("/transaction/simulate")
async def simulate_transaction(
    transaction_base64: str = Body(..., embed=True),
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Simulate a Solana transaction and analyze its effects.
    
    Args:
        transaction_base64: Base64-encoded transaction
        
    Returns:
        Simulation results and analysis
    """
    if not transaction_base64:
        raise HTTPException(status_code=400, detail="Transaction data is required")
    
    result = await analyzer.simulate_transaction(transaction_base64)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Simulation failed"))
    
    return result

@router.get("/transaction/analyze/{transaction_signature}")
async def analyze_transaction(
    transaction_signature: str,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Analyze a transaction that has already been executed.
    
    Args:
        transaction_signature: The transaction signature
        
    Returns:
        Transaction analysis results
    """
    if not transaction_signature:
        raise HTTPException(status_code=400, detail="Transaction signature is required")
    
    result = await analyzer.analyze_transaction(transaction_signature)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
    
    return result

class ImpermanentLossRequest(BaseModel):
    """Request model for impermanent loss calculation."""
    pool_address: str = Field(..., description="Liquidity pool address")
    initial_price: float = Field(..., gt=0, description="Initial price when liquidity was added")
    current_price: float = Field(..., gt=0, description="Current price")

@router.get("/defi/protocol/{address}")
async def identify_defi_protocol(
    address: str,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Identify which DeFi protocol the given address belongs to.
    
    Args:
        address: The address to analyze
        
    Returns:
        Protocol identification results
    """
    if not validate_solana_address(address):
        raise HTTPException(status_code=400, detail="Invalid Solana address")
    
    result = await analyzer.identify_defi_protocol(address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Protocol identification failed"))
    
    return result

@router.get("/defi/pool/{pool_address}")
async def analyze_liquidity_pool(
    pool_address: str,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Analyze a liquidity pool.
    
    Args:
        pool_address: The pool address to analyze
        
    Returns:
        Liquidity pool analysis
    """
    if not validate_solana_address(pool_address):
        raise HTTPException(status_code=400, detail="Invalid Solana address")
    
    result = await analyzer.analyze_liquidity_pool(pool_address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Liquidity pool analysis failed"))
    
    return result

@router.get("/defi/lending/{position_address}")
async def analyze_lending_position(
    position_address: str,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Analyze a lending position.
    
    Args:
        position_address: The position address to analyze
        
    Returns:
        Lending position analysis
    """
    if not validate_solana_address(position_address):
        raise HTTPException(status_code=400, detail="Invalid Solana address")
    
    result = await analyzer.analyze_lending_position(position_address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Lending position analysis failed"))
    
    return result

@router.get("/defi/staking/{position_address}")
async def analyze_staking_position(
    position_address: str,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Analyze a staking position.
    
    Args:
        position_address: The position address to analyze
        
    Returns:
        Staking position analysis
    """
    if not validate_solana_address(position_address):
        raise HTTPException(status_code=400, detail="Invalid Solana address")
    
    result = await analyzer.analyze_staking_position(position_address)
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Staking position analysis failed"))
    
    return result

@router.post("/defi/impermanent-loss")
async def calculate_impermanent_loss(
    request: ImpermanentLossRequest,
    analyzer: SolanaProgramAnalyzerService = Depends(get_solana_program_analyzer_service)
):
    """
    Calculate impermanent loss for a liquidity position.
    
    Args:
        request: The request containing pool address and price information
        
    Returns:
        Impermanent loss calculation
    """
    result = await analyzer.calculate_impermanent_loss(
        request.pool_address,
        request.initial_price,
        request.current_price
    )
    
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Impermanent loss calculation failed"))
    
    return result 