"""
Visualization utilities for Telegram bot.
Provides chart generation and other visual elements.
"""
import io
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from datetime import datetime, timedelta
from telegram import InputFile

from src.bot.message_templates import Emoji

# Configure matplotlib for non-interactive backend
matplotlib.use('Agg')

# Set up logging
logger = logging.getLogger(__name__)

class Visualizer:
    """Visualization tools for Telegram bot."""
    
    @staticmethod
    def generate_price_chart(
        price_data: List[Dict[str, Any]], 
        token_symbol: str,
        days: int = 7
    ) -> Optional[io.BytesIO]:
        """
        Generate a price chart image.
        
        Args:
            price_data: List of price data points with timestamp and price
            token_symbol: Token symbol for chart title
            days: Number of days to display
            
        Returns:
            BytesIO: Image buffer or None if error
        """
        try:
            # Extract dates and prices
            dates = [datetime.fromtimestamp(item['timestamp']) for item in price_data]
            prices = [float(item['price']) for item in price_data]
            
            # Create figure and axis
            plt.figure(figsize=(10, 6))
            plt.plot(dates, prices, 'b-', linewidth=2)
            
            # Set title and labels
            plt.title(f"{token_symbol} Price - Last {days} Days", fontsize=16)
            plt.xlabel("Date", fontsize=12)
            plt.ylabel("Price (USD)", fontsize=12)
            plt.grid(True, linestyle='--', alpha=0.7)
            
            # Format x-axis dates
            plt.gcf().autofmt_xdate()
            
            # Add current price annotation
            if prices:
                current_price = prices[-1]
                plt.annotate(
                    f"${current_price:.4f}", 
                    xy=(dates[-1], current_price),
                    xytext=(10, 0),
                    textcoords="offset points",
                    fontsize=12,
                    color='darkblue',
                    weight='bold'
                )
            
            # Color background based on price trend
            if len(prices) > 1:
                if prices[-1] > prices[0]:
                    plt.gca().set_facecolor('#e6ffe6')  # Light green
                elif prices[-1] < prices[0]:
                    plt.gca().set_facecolor('#ffe6e6')  # Light red
            
            # Save chart to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generating price chart: {e}")
            return None
    
    @staticmethod
    def generate_risk_radar_chart(risk_factors: Dict[str, float]) -> Optional[io.BytesIO]:
        """
        Generate a radar chart for risk factors.
        
        Args:
            risk_factors: Dictionary of risk factor names and scores (0-1)
            
        Returns:
            BytesIO: Image buffer or None if error
        """
        try:
            # Prepare data
            categories = list(risk_factors.keys())
            formatted_categories = [c.replace('_', ' ').title() for c in categories]
            values = list(risk_factors.values())
            
            # Add the first value at the end to close the polygon
            values.append(values[0])
            formatted_categories.append(formatted_categories[0])
            
            # Calculate angle for each category
            angles = np.linspace(0, 2*np.pi, len(categories), endpoint=False).tolist()
            angles += angles[:1]  # Close the polygon
            
            # Create figure and polar axis
            fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
            
            # Plot data
            ax.plot(angles, values, 'o-', linewidth=2, color='red')
            ax.fill(angles, values, alpha=0.25, color='red')
            
            # Set category labels
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(formatted_categories[:-1])
            
            # Set y-axis limits
            ax.set_ylim(0, 1)
            ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
            ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'])
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.7)
            
            # Set title
            plt.title('Risk Factor Analysis', size=15, color='darkred', weight='bold')
            
            # Save chart to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generating risk radar chart: {e}")
            return None
    
    @staticmethod
    def generate_holder_distribution_chart(
        holders_data: List[Dict[str, Any]]
    ) -> Optional[io.BytesIO]:
        """
        Generate a pie chart for token holder distribution.
        
        Args:
            holders_data: List of holder data with address and percentage
            
        Returns:
            BytesIO: Image buffer or None if error
        """
        try:
            # Prepare data
            if len(holders_data) > 10:
                # If more than 10 holders, group the smallest ones
                sorted_holders = sorted(holders_data, key=lambda x: x['percentage'], reverse=True)
                top_holders = sorted_holders[:9]
                others_pct = sum(h['percentage'] for h in sorted_holders[9:])
                
                labels = [f"{h.get('label', 'Wallet')} ({h['percentage']:.1f}%)" for h in top_holders]
                labels.append(f"Others ({others_pct:.1f}%)")
                
                sizes = [h['percentage'] for h in top_holders]
                sizes.append(others_pct)
            else:
                labels = [f"{h.get('label', 'Wallet')} ({h['percentage']:.1f}%)" for h in holders_data]
                sizes = [h['percentage'] for h in holders_data]
            
            # Create colors
            colors = plt.cm.tab20.colors[:len(labels)]
            
            # Create figure and axis
            plt.figure(figsize=(10, 8))
            
            # Create pie chart
            wedges, texts, autotexts = plt.pie(
                sizes, 
                labels=None,
                autopct='',
                colors=colors,
                startangle=90,
                wedgeprops={'edgecolor': 'w', 'linewidth': 1}
            )
            
            # Add legend
            plt.legend(
                wedges, 
                labels,
                title="Holders",
                loc="center left",
                bbox_to_anchor=(1, 0, 0.5, 1)
            )
            
            # Set title
            plt.title('Token Holder Distribution', size=15)
            
            # Set aspect ratio to be equal
            plt.axis('equal')
            
            # Save chart to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generating holder distribution chart: {e}")
            return None
    
    @staticmethod
    def generate_volume_chart(
        volume_data: List[Dict[str, Any]],
        token_symbol: str,
        days: int = 7
    ) -> Optional[io.BytesIO]:
        """
        Generate a volume chart image.
        
        Args:
            volume_data: List of volume data points with timestamp and volume
            token_symbol: Token symbol for chart title
            days: Number of days to display
            
        Returns:
            BytesIO: Image buffer or None if error
        """
        try:
            # Extract dates and volumes
            dates = [datetime.fromtimestamp(item['timestamp']) for item in volume_data]
            volumes = [float(item['volume']) for item in volume_data]
            
            # Create figure and axis
            plt.figure(figsize=(10, 6))
            
            # Plot the bar chart
            plt.bar(dates, volumes, width=0.8, alpha=0.7, color='blue')
            
            # Set title and labels
            plt.title(f"{token_symbol} Trading Volume - Last {days} Days", fontsize=16)
            plt.xlabel("Date", fontsize=12)
            plt.ylabel("Volume (USD)", fontsize=12)
            plt.grid(True, linestyle='--', alpha=0.5, axis='y')
            
            # Format y-axis with K, M, B suffixes
            plt.gca().yaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, loc: f"${x/1000000:.1f}M" if x >= 1000000 else f"${x/1000:.1f}K")
            )
            
            # Format x-axis dates
            plt.gcf().autofmt_xdate()
            
            # Add average line
            avg_volume = sum(volumes) / len(volumes) if volumes else 0
            plt.axhline(y=avg_volume, color='r', linestyle='--', alpha=0.7)
            plt.annotate(
                f"Avg: ${avg_volume/1000000:.1f}M" if avg_volume >= 1000000 else f"Avg: ${avg_volume/1000:.1f}K",
                xy=(0.02, 0.95),
                xycoords='axes fraction',
                fontsize=10,
                color='red'
            )
            
            # Save chart to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generating volume chart: {e}")
            return None
    
    @staticmethod
    def generate_risk_indicator_image(risk_level: str) -> Optional[io.BytesIO]:
        """
        Generate a simple risk level indicator image.
        
        Args:
            risk_level: Risk level (low, medium, high, critical)
            
        Returns:
            BytesIO: Image buffer or None if error
        """
        try:
            # Map risk level to color
            colors = {
                'low': 'green',
                'medium': 'yellow',
                'high': 'red',
                'critical': 'darkred',
                'unknown': 'gray'
            }
            
            risk_level = risk_level.lower()
            color = colors.get(risk_level, 'gray')
            
            # Create figure and axis
            plt.figure(figsize=(3, 1))
            ax = plt.gca()
            
            # Hide axes
            ax.set_axis_off()
            
            # Create the indicator
            circle = plt.Circle((0.5, 0.5), 0.4, color=color)
            ax.add_patch(circle)
            
            # Add text
            plt.text(
                0.5, 0.5, 
                risk_level.upper(), 
                ha='center', 
                va='center', 
                fontsize=14, 
                color='white', 
                weight='bold'
            )
            
            # Save chart to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generating risk indicator: {e}")
            return None
    
    @staticmethod
    async def send_chart(update, context, chart_buffer, caption: str = None) -> None:
        """
        Send a chart image to the user.
        
        Args:
            update: Telegram update
            context: Callback context
            chart_buffer: Image buffer
            caption: Optional caption for the image
        """
        if chart_buffer is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{Emoji.ERROR} Failed to generate chart."
            )
            return
        
        try:
            # Prepare photo input
            input_file = InputFile(chart_buffer, filename='chart.png')
            
            # Send photo
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=input_file,
                caption=caption,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error sending chart: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{Emoji.ERROR} Failed to send chart: {str(e)}"
            )


# Singleton instance
visualizer = Visualizer() 