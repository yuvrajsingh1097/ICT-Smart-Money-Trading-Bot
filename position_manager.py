"""
Advanced Position Management Module
Manages entries, exits, scaling, and trailing stops alongside core backtester
Maintains risk/reward discipline while handling multi-leg positions
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PositionStatus(Enum):
    """Position lifecycle states"""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PARTIAL = "PARTIAL"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"


@dataclass
class PositionLeg:
    """Individual position entry in a multi-leg setup"""
    entry_price: float
    entry_index: int
    quantity: float
    stop_loss: float
    take_profit: float
    status: PositionStatus = PositionStatus.PENDING
    exit_price: Optional[float] = None
    exit_index: Optional[int] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0


@dataclass
class PositionConfig:
    """Configuration for position management"""
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 0.015  # 1.5% trailing stop
    pyramid_enabled: bool = True
    max_legs: int = 3  # Max 3 entries per position
    leg_sizing: str = 'equal'  # 'equal', 'increasing', 'decreasing'
    scale_out_enabled: bool = True
    scale_out_pct: float = 0.33  # Scale out at 33% of TP reached
    breakeven_on_scale: bool = True  # Move stop to breakeven after scale


class AdvancedPositionManager:
    """Manage complex multi-leg positions with advanced exits"""
    
    def __init__(self, config: PositionConfig = None):
        self.config = config or PositionConfig()
        self.positions: List[PositionLeg] = []
        self.closed_positions: List[PositionLeg] = []
        self.stats = {
            'total_positions': 0,
            'avg_holding_bars': 0,
            'scale_outs': 0,
            'trailing_stops': 0,
            'breakeven_triggers': 0
        }
    
    def add_position(self, entry_price: float, entry_index: int, 
                    stop_loss: float, take_profit: float, 
                    quantity: float = 1.0) -> PositionLeg:
        """Add new position leg"""
        leg = PositionLeg(
            entry_price=entry_price,
            entry_index=entry_index,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        # Check pyramid limit
        active_legs = len([p for p in self.positions if p.status == PositionStatus.ACTIVE])
        if active_legs < self.config.max_legs:
            self.positions.append(leg)
            self.stats['total_positions'] += 1
            return leg
        
        return None
    
    def calculate_trailing_stop(self, current_price: float, entry_price: float,
                              current_stop: float, signal_type: str) -> float:
        """Calculate trailing stop based on price movement"""
        if signal_type == 'LONG':
            # Trailing stop for longs: tracks up from entry
            profit_amount = current_price - entry_price
            trailing_level = current_price - (current_price * self.config.trailing_stop_pct)
            
            # Only move stop up, never down
            return max(current_stop, trailing_level)
        
        else:  # SHORT
            # Trailing stop for shorts: tracks down from entry
            profit_amount = entry_price - current_price
            trailing_level = current_price + (current_price * self.config.trailing_stop_pct)
            
            # Only move stop down, never up
            return min(current_stop, trailing_level)
    
    def calculate_pyramid_entry(self, base_entry: float, leg_number: int,
                              signal_type: str) -> float:
        """Calculate pyramid entry prices for multiple legs"""
        pyramid_spacing = 0.003  # 0.3% spacing between legs
        
        if signal_type == 'LONG':
            return base_entry - (base_entry * pyramid_spacing * leg_number)
        else:
            return base_entry + (base_entry * pyramid_spacing * leg_number)
    
    def update_position(self, leg: PositionLeg, current_price: float, 
                       current_index: int, signal_type: str) -> Dict:
        """Update position and check for exits/scaling"""
        updates = {
            'scaled_out': False,
            'stopped': False,
            'at_breakeven': False,
            'new_stop': leg.stop_loss,
            'status': leg.status
        }
        
        if signal_type == 'LONG':
            # Check stop loss
            if current_price <= leg.stop_loss:
                leg.status = PositionStatus.STOPPED
                leg.exit_price = leg.stop_loss
                leg.exit_index = current_index
                leg.pnl = (leg.stop_loss - leg.entry_price) * leg.quantity
                leg.pnl_percent = (leg.pnl / (leg.entry_price * leg.quantity)) * 100
                updates['stopped'] = True
                self.stats['trailing_stops'] += 1
            
            # Check take profit
            elif current_price >= leg.take_profit:
                leg.status = PositionStatus.CLOSED
                leg.exit_price = leg.take_profit
                leg.exit_index = current_index
                leg.pnl = (leg.take_profit - leg.entry_price) * leg.quantity
                leg.pnl_percent = (leg.pnl / (leg.entry_price * leg.quantity)) * 100
            
            # Scale out at 50% TP reached
            elif self.config.scale_out_enabled and current_price > leg.entry_price:
                tp_distance = leg.take_profit - leg.entry_price
                current_progress = current_price - leg.entry_price
                progress_pct = current_progress / tp_distance
                
                if progress_pct >= self.config.scale_out_pct and leg.quantity > 0.5:
                    scale_qty = leg.quantity * 0.5
                    partial_pnl = (current_price - leg.entry_price) * scale_qty
                    
                    leg.quantity -= scale_qty
                    leg.status = PositionStatus.PARTIAL
                    updates['scaled_out'] = True
                    self.stats['scale_outs'] += 1
                    
                    # Move stop to breakeven on scale out
                    if self.config.breakeven_on_scale:
                        leg.stop_loss = leg.entry_price
                        updates['at_breakeven'] = True
                        self.stats['breakeven_triggers'] += 1
            
            # Trailing stop
            elif self.config.use_trailing_stop and current_price > leg.entry_price:
                new_stop = self.calculate_trailing_stop(current_price, leg.entry_price,
                                                       leg.stop_loss, signal_type)
                if new_stop > leg.stop_loss:
                    leg.stop_loss = new_stop
                    updates['new_stop'] = new_stop
        
        else:  # SHORT
            # Check stop loss
            if current_price >= leg.stop_loss:
                leg.status = PositionStatus.STOPPED
                leg.exit_price = leg.stop_loss
                leg.exit_index = current_index
                leg.pnl = (leg.entry_price - leg.stop_loss) * leg.quantity
                leg.pnl_percent = (leg.pnl / (leg.entry_price * leg.quantity)) * 100
                updates['stopped'] = True
                self.stats['trailing_stops'] += 1
            
            # Check take profit
            elif current_price <= leg.take_profit:
                leg.status = PositionStatus.CLOSED
                leg.exit_price = leg.take_profit
                leg.exit_index = current_index
                leg.pnl = (leg.entry_price - leg.take_profit) * leg.quantity
                leg.pnl_percent = (leg.pnl / (leg.entry_price * leg.quantity)) * 100
            
            # Scale out
            elif self.config.scale_out_enabled and current_price < leg.entry_price:
                tp_distance = leg.entry_price - leg.take_profit
                current_progress = leg.entry_price - current_price
                progress_pct = current_progress / tp_distance
                
                if progress_pct >= self.config.scale_out_pct and leg.quantity > 0.5:
                    scale_qty = leg.quantity * 0.5
                    
                    leg.quantity -= scale_qty
                    leg.status = PositionStatus.PARTIAL
                    updates['scaled_out'] = True
                    self.stats['scale_outs'] += 1
                    
                    if self.config.breakeven_on_scale:
                        leg.stop_loss = leg.entry_price
                        updates['at_breakeven'] = True
                        self.stats['breakeven_triggers'] += 1
            
            # Trailing stop
            elif self.config.use_trailing_stop and current_price < leg.entry_price:
                new_stop = self.calculate_trailing_stop(current_price, leg.entry_price,
                                                       leg.stop_loss, signal_type)
                if new_stop < leg.stop_loss:
                    leg.stop_loss = new_stop
                    updates['new_stop'] = new_stop
        
        updates['status'] = leg.status.value
        return updates
    
    def close_all_positions(self, close_price: float, close_index: int) -> List[PositionLeg]:
        """Force close all open positions at market price"""
        closed = []
        for leg in self.positions:
            if leg.status in [PositionStatus.ACTIVE, PositionStatus.PARTIAL]:
                leg.exit_price = close_price
                leg.exit_index = close_index
                leg.status = PositionStatus.CLOSED
                
                # Recalculate PNL
                if leg.entry_price > 0:
                    leg.pnl = (close_price - leg.entry_price) * leg.quantity
                    leg.pnl_percent = (leg.pnl / (leg.entry_price * leg.quantity)) * 100
                
                closed.append(leg)
                self.closed_positions.append(leg)
        
        self.positions = [p for p in self.positions if p.status not in 
                         [PositionStatus.CLOSED, PositionStatus.STOPPED]]
        return closed
    
    def get_position_summary(self) -> Dict:
        """Get summary of all positions"""
        all_positions = self.positions + self.closed_positions
        
        if not all_positions:
            return {'error': 'No positions'}
        
        total_pnl = sum(p.pnl for p in all_positions)
        winners = sum(1 for p in all_positions if p.pnl > 0)
        
        holding_bars = [p.exit_index - p.entry_index for p in all_positions 
                       if p.exit_index is not None]
        avg_bars = np.mean(holding_bars) if holding_bars else 0
        
        return {
            'total_positions': len(all_positions),
            'active_positions': len(self.positions),
            'closed_positions': len(self.closed_positions),
            'total_pnl': total_pnl,
            'total_pnl_percent': f"{(total_pnl / (len(all_positions) * 100)):.2f}%",
            'win_rate': f"{(winners/len(all_positions)*100):.1f}%",
            'avg_holding_bars': f"{avg_bars:.0f}",
            'scale_outs': self.stats['scale_outs'],
            'trailing_stops_triggered': self.stats['trailing_stops'],
            'breakeven_moves': self.stats['breakeven_triggers']
        }


class RiskAdjustmentEngine:
    """Dynamic risk adjustment based on equity curve"""
    
    @staticmethod
    def adjust_position_size(equity: float, account_risk_pct: float = 0.02,
                           drawdown_pct: float = 0.0) -> float:
        """
        Adjust position size based on current drawdown
        Reduces size during drawdown, increases during gains
        """
        # Reduce size by 50% if in >10% drawdown
        if drawdown_pct > 0.10:
            return account_risk_pct * 0.5
        
        # Reduce size by 25% if in >5% drawdown
        elif drawdown_pct > 0.05:
            return account_risk_pct * 0.75
        
        # Standard size on recovery
        return account_risk_pct
    
    @staticmethod
    def calculate_max_consecutive_losses(trades: List[Dict]) -> int:
        """Calculate longest losing streak"""
        if not trades:
            return 0
        
        max_streak = 0
        current_streak = 0
        
        for trade in trades:
            if trade.get('pnl', 0) < 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    @staticmethod
    def should_reduce_size(stats: Dict) -> bool:
        """Determine if position sizing should be reduced"""
        # Reduce if: 3+ losses in a row
        if stats.get('consecutive_losses', 0) >= 3:
            return True
        
        # Reduce if: drawdown > 15%
        if stats.get('drawdown_pct', 0) > 0.15:
            return True
        
        # Reduce if: win rate drops below 45%
        if stats.get('win_rate', 100) < 45:
            return True
        
        return False


# Usage Example:
if __name__ == "__main__":
    print("Position Management Module Loaded")
    print("\nFeatures:")
    print("✓ Multi-leg pyramiding (up to 3 legs)")
    print("✓ Trailing stops with customizable percentages")
    print("✓ Scale-out management (partial exits)")
    print("✓ Breakeven moves after scaling")
    print("✓ Risk adjustment during drawdowns")
    print("\nImport: from position_manager import AdvancedPositionManager, RiskAdjustmentEngine")
