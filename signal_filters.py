"""
Advanced Signal Filtering & Confirmation Module
Reduces false signals through multi-layer confirmation without changing core logic
Works alongside existing backtester - import and apply filters to signals
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Dict
from dataclasses import dataclass


@dataclass
class FilterConfig:
    """Configuration for signal filters"""
    min_fvg_size: float = 0.0005  # Minimum FVG % of price
    max_fvg_age: int = 20  # Max candles before FVG expires
    liquidity_buffer: float = 0.002  # Buffer around pools
    volume_threshold: float = 1.2  # Volume > MA multiplier
    rsi_extremes: Tuple[int, int] = (25, 75)  # Oversold/overbought
    macd_confirmation: bool = True
    volume_confirmation: bool = True


class SignalFilter:
    """Multi-layer signal confirmation system"""
    
    def __init__(self, config: FilterConfig = None):
        self.config = config or FilterConfig()
        self.stats = {
            'total_signals': 0,
            'filtered_signals': 0,
            'fvg_filters': 0,
            'volume_filters': 0,
            'rsi_filters': 0,
            'macd_filters': 0,
            'confirmed_signals': 0
        }
    
    def calculate_rsi(self, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI for momentum confirmation"""
        delta = np.diff(closes)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.convolve(gain, np.ones(period)/period, mode='valid')
        avg_loss = np.convolve(loss, np.ones(period)/period, mode='valid')
        
        rsi = np.full_like(closes, np.nan)
        rs = avg_gain / (avg_loss + 1e-10)
        rsi[period:] = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_macd(self, closes: np.ndarray, 
                      fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate MACD for trend confirmation"""
        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)
        macd = ema_fast - ema_slow
        signal_line = self._ema(macd, signal)
        return macd, signal_line
    
    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """Exponential moving average"""
        ema = np.full_like(data, np.nan)
        multiplier = 2 / (period + 1)
        ema[period-1] = np.mean(data[:period])
        for i in range(period, len(data)):
            ema[i] = data[i] * multiplier + ema[i-1] * (1 - multiplier)
        return ema
    
    def filter_fvg_quality(self, df: pd.DataFrame, signal_idx: int, 
                          signal_type: str) -> bool:
        """Confirm FVG size and age quality"""
        if signal_idx < 3:
            return False
        
        high = df['High'].iloc[signal_idx]
        low = df['Low'].iloc[signal_idx]
        close = df['Close'].iloc[signal_idx]
        
        # Check FVG size
        fvg_size = (high - low) / close
        if fvg_size < self.config.min_fvg_size:
            self.stats['fvg_filters'] += 1
            return False
        
        # Check candle structure
        body_size = abs(close - df['Open'].iloc[signal_idx])
        wick_size = high - low
        
        # Prefer defined structure
        if body_size / wick_size < 0.3:
            return False
        
        return True
    
    def filter_volume_confirmation(self, volumes: np.ndarray, 
                                  signal_idx: int, period: int = 20) -> bool:
        """Confirm signal with volume surge"""
        if signal_idx < period:
            return True  # Not enough history
        
        volume_ma = np.mean(volumes[signal_idx-period:signal_idx])
        current_vol = volumes[signal_idx]
        
        if current_vol < volume_ma * self.config.volume_threshold:
            self.stats['volume_filters'] += 1
            return False
        
        return True
    
    def filter_rsi_confirmation(self, closes: np.ndarray, 
                               signal_idx: int, signal_type: str) -> bool:
        """Confirm signal with RSI extremes"""
        rsi = self.calculate_rsi(closes)
        
        if np.isnan(rsi[signal_idx]):
            return True
        
        current_rsi = rsi[signal_idx]
        
        if signal_type == 'LONG':
            # Long in oversold
            if current_rsi > self.config.rsi_extremes[0]:
                self.stats['rsi_filters'] += 1
                return False
        else:
            # Short in overbought
            if current_rsi < self.config.rsi_extremes[1]:
                self.stats['rsi_filters'] += 1
                return False
        
        return True
    
    def filter_macd_confirmation(self, closes: np.ndarray, signal_idx: int, 
                                signal_type: str) -> bool:
        """Confirm signal with MACD trend"""
        if signal_idx < 26:
            return True
        
        macd, signal_line = self.calculate_macd(closes)
        
        if np.isnan(macd[signal_idx]):
            return True
        
        if signal_type == 'LONG':
            # MACD above signal line
            if macd[signal_idx] < signal_line[signal_idx]:
                self.stats['macd_filters'] += 1
                return False
        else:
            # MACD below signal line
            if macd[signal_idx] > signal_line[signal_idx]:
                self.stats['macd_filters'] += 1
                return False
        
        return True
    
    def apply_all_filters(self, df: pd.DataFrame, signal_idx: int, 
                         signal_type: str) -> bool:
        """Apply all confirmation filters"""
        self.stats['total_signals'] += 1
        
        # Core filters
        if not self.filter_fvg_quality(df, signal_idx, signal_type):
            self.stats['filtered_signals'] += 1
            return False
        
        if self.config.volume_confirmation:
            if not self.filter_volume_confirmation(df['Volume'].values, signal_idx):
                self.stats['filtered_signals'] += 1
                return False
        
        if not self.filter_rsi_confirmation(df['Close'].values, signal_idx, signal_type):
            self.stats['filtered_signals'] += 1
            return False
        
        if self.config.macd_confirmation:
            if not self.filter_macd_confirmation(df['Close'].values, signal_idx, signal_type):
                self.stats['filtered_signals'] += 1
                return False
        
        self.stats['confirmed_signals'] += 1
        return True
    
    def get_filter_report(self) -> Dict:
        """Get filtering statistics"""
        total = self.stats['total_signals']
        if total == 0:
            return {'error': 'No signals analyzed'}
        
        return {
            'total_signals': total,
            'confirmed_signals': self.stats['confirmed_signals'],
            'filtered_out': self.stats['filtered_signals'],
            'confirmation_rate': f"{(self.stats['confirmed_signals']/total*100):.1f}%",
            'fvg_filters': self.stats['fvg_filters'],
            'volume_filters': self.stats['volume_filters'],
            'rsi_filters': self.stats['rsi_filters'],
            'macd_filters': self.stats['macd_filters']
        }


class SmartMoneyDetector:
    """Detect Smart Money accumulation/distribution patterns"""
    
    @staticmethod
    def detect_smt_divergence(asset_a: pd.DataFrame, asset_b: pd.DataFrame, 
                             window: int = 20) -> List[Dict]:
        """
        Detect Smart Money Divergence (SMT) between two correlated assets
        Returns: List of divergence signals with timestamps and types
        """
        divergences = []
        
        # Ensure same length
        min_len = min(len(asset_a), len(asset_b))
        a_highs = asset_a['High'].values[-min_len:]
        a_lows = asset_a['Low'].values[-min_len:]
        b_highs = asset_b['High'].values[-min_len:]
        b_lows = asset_b['Low'].values[-min_len:]
        
        for i in range(window, len(a_highs)-1):
            # Detect bearish SMT: A makes HH while B makes LH
            if (a_highs[i] > a_highs[i-window] and 
                b_highs[i] < b_highs[i-window] and
                b_highs[i-1] > b_highs[i-window]):
                
                divergences.append({
                    'index': i,
                    'type': 'BEARISH_SMT',
                    'strength': (a_highs[i] - a_highs[i-window]) / a_highs[i-window],
                    'message': 'Asset A HH, Asset B LH - Distribution detected'
                })
            
            # Detect bullish SMT: A makes LL while B makes HL
            elif (a_lows[i] < a_lows[i-window] and 
                  b_lows[i] > b_lows[i-window] and
                  b_lows[i-1] < b_lows[i-window]):
                
                divergences.append({
                    'index': i,
                    'type': 'BULLISH_SMT',
                    'strength': (a_lows[i-window] - a_lows[i]) / a_lows[i-window],
                    'message': 'Asset A LL, Asset B HL - Accumulation detected'
                })
        
        return divergences
    
    @staticmethod
    def detect_order_block_break(df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """Detect breaks above/below order blocks with reversal potential"""
        blocks = []
        
        for i in range(lookback, len(df)):
            # High order block (previous resistance)
            high_block = df['High'].iloc[i-lookback:i].max()
            
            # Low order block (previous support)
            low_block = df['Low'].iloc[i-lookback:i].min()
            
            current_close = df['Close'].iloc[i]
            current_high = df['High'].iloc[i]
            current_low = df['Low'].iloc[i]
            
            # Bullish: Close reclaims above broken low
            if current_close > low_block and df['Close'].iloc[i-1] < low_block:
                blocks.append({
                    'index': i,
                    'type': 'BULLISH_BLOCK_BREAK',
                    'level': low_block,
                    'confluence': 'Price rejected below support, now reclaiming'
                })
            
            # Bearish: Close reclaims below broken high
            if current_close < high_block and df['Close'].iloc[i-1] > high_block:
                blocks.append({
                    'index': i,
                    'type': 'BEARISH_BLOCK_BREAK',
                    'level': high_block,
                    'confluence': 'Price rejected above resistance, now reclaiming'
                })
        
        return blocks


# Usage Example (in your backtester):
if __name__ == "__main__":
    print("Signal Filter Module Loaded")
    print("Import: from signal_filters import SignalFilter, SmartMoneyDetector")
    print("\nUsage:")
    print("  filter = SignalFilter()")
    print("  is_valid = filter.apply_all_filters(df, signal_idx, 'LONG')")
    print("  report = filter.get_filter_report()")
