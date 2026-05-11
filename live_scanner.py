"""
Real-Time Market Scanner & Alert Module
Scans multiple timeframes for setup confluence without changing core logic
Generates alerts with confidence scores for live trading
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class MarketAlert:
    """Market setup alert with confidence scoring"""
    symbol: str
    timeframe: str
    setup_type: str
    signal_direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence_score: float
    severity: AlertSeverity
    confluence_factors: List[str]
    timestamp: str
    analysis_notes: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        d = asdict(self)
        d['severity'] = self.severity.value
        return d


class MultiTimeframeAnalyzer:
    """Analyze setups across multiple timeframes for confluence"""
    
    def __init__(self):
        self.signals = {
            '1m': [],
            '5m': [],
            '15m': [],
            '1h': [],
            '4h': [],
            '1d': []
        }
        self.confluence_threshold = 3  # Min timeframes showing same signal
    
    def add_signal(self, timeframe: str, signal_type: str, 
                  entry: float, stop: float, tp: float) -> None:
        """Add signal from different timeframe"""
        if timeframe in self.signals:
            self.signals[timeframe].append({
                'type': signal_type,
                'entry': entry,
                'stop': stop,
                'tp': tp,
                'timestamp': datetime.now()
            })
    
    def detect_confluence(self, symbol: str, current_price: float) -> List[Dict]:
        """Detect confluence across timeframes"""
        confluences = []
        
        # Count bullish signals across timeframes
        bullish_count = sum(1 for tf in self.signals.values() 
                          if any(s['type'] == 'LONG' for s in tf))
        
        # Count bearish signals across timeframes
        bearish_count = sum(1 for tf in self.signals.values() 
                           if any(s['type'] == 'SHORT' for s in tf))
        
        # Strong bullish confluence
        if bullish_count >= self.confluence_threshold:
            confluences.append({
                'type': 'STRONG_BULLISH_CONFLUENCE',
                'strength': bullish_count,
                'timeframes_aligned': bullish_count,
                'confidence': min(95, 60 + (bullish_count * 8))
            })
        
        # Strong bearish confluence
        if bearish_count >= self.confluence_threshold:
            confluences.append({
                'type': 'STRONG_BEARISH_CONFLUENCE',
                'strength': bearish_count,
                'timeframes_aligned': bearish_count,
                'confidence': min(95, 60 + (bearish_count * 8))
            })
        
        return confluences
    
    def get_optimal_entry(self, timeframe_signals: Dict) -> Optional[Dict]:
        """Find optimal entry by comparing signals across timeframes"""
        # Longer timeframes have higher weight
        weight_map = {'1d': 5, '4h': 4, '1h': 3, '15m': 2, '5m': 1.5, '1m': 1}
        
        weighted_longs = 0
        weighted_shorts = 0
        
        for tf, signal_list in timeframe_signals.items():
            weight = weight_map.get(tf, 1)
            for signal in signal_list:
                if signal['type'] == 'LONG':
                    weighted_longs += weight
                else:
                    weighted_shorts += weight
        
        if weighted_longs > weighted_shorts:
            return {'direction': 'LONG', 'weight': weighted_longs}
        elif weighted_shorts > weighted_longs:
            return {'direction': 'SHORT', 'weight': weighted_shorts}
        
        return None


class LiveSetupScanner:
    """Scan for live trading setups with filtering"""
    
    def __init__(self, min_confidence: float = 70.0):
        self.min_confidence = min_confidence
        self.scanned_symbols = {}
        self.alerts: List[MarketAlert] = []
    
    def scan_symbol(self, df: pd.DataFrame, symbol: str, 
                   current_price: float) -> Optional[MarketAlert]:
        """
        Scan a symbol for trading setups
        Returns alert if setup meets confidence threshold
        """
        if len(df) < 50:
            return None
        
        # Detect key structures
        structures = self._detect_structures(df)
        
        # Calculate confluence
        confluence_score = self._score_confluence(structures)
        
        if confluence_score < self.min_confidence:
            return None
        
        # Build alert
        setup_type = structures.get('primary_setup', 'UNKNOWN')
        direction = structures.get('direction', 'UNKNOWN')
        
        if direction == 'UNKNOWN':
            return None
        
        entry = self._calculate_optimal_entry(df, direction)
        stop, tp = self._calculate_risk_reward(df, direction, entry)
        
        severity = self._determine_severity(confluence_score)
        
        alert = MarketAlert(
            symbol=symbol,
            timeframe='REAL_TIME',
            setup_type=setup_type,
            signal_direction=direction,
            entry_price=entry,
            stop_loss=stop,
            take_profit=tp,
            confidence_score=confluence_score,
            severity=severity,
            confluence_factors=structures.get('factors', []),
            timestamp=datetime.now().isoformat(),
            analysis_notes=self._generate_notes(structures, confluence_score)
        )
        
        self.alerts.append(alert)
        return alert
    
    def _detect_structures(self, df: pd.DataFrame) -> Dict:
        """Detect market structures in the data"""
        structures = {'factors': [], 'direction': None}
        
        # Check for FVG
        fvg_detected = self._check_fvg(df)
        if fvg_detected:
            structures['factors'].append('FVG Present')
            structures['direction'] = fvg_detected
        
        # Check for liquidity pool
        pools = self._check_liquidity_pools(df)
        if pools:
            structures['factors'].append(f'Liquidity Pool ({pools})')
        
        # Check for market structure (HH/HL or LH/LL)
        ms = self._check_market_structure(df)
        if ms:
            structures['factors'].append(f'MS: {ms}')
            if 'LONG' in ms:
                structures['direction'] = 'LONG'
            else:
                structures['direction'] = 'SHORT'
        
        # Check momentum
        momentum = self._check_momentum(df)
        if momentum:
            structures['factors'].append(f'Momentum: {momentum}')
        
        structures['primary_setup'] = 'ICT_MULTICONFLUENCE'
        return structures
    
    @staticmethod
    def _check_fvg(df: pd.DataFrame) -> Optional[str]:
        """Check for Fair Value Gap"""
        if len(df) < 3:
            return None
        
        # Bullish FVG: gap up
        if df['Low'].iloc[-1] > df['High'].iloc[-3]:
            return 'LONG'
        
        # Bearish FVG: gap down
        if df['High'].iloc[-1] < df['Low'].iloc[-3]:
            return 'SHORT'
        
        return None
    
    @staticmethod
    def _check_liquidity_pools(df: pd.DataFrame) -> Optional[str]:
        """Check for equal highs/lows (liquidity pools)"""
        highs = df['High'].tail(20).values
        lows = df['Low'].tail(20).values
        
        # Check for repeated highs
        high_diff = np.diff(highs)
        if np.any(np.abs(high_diff) < 0.001):
            return 'HIGH'
        
        # Check for repeated lows
        low_diff = np.diff(lows)
        if np.any(np.abs(low_diff) < 0.001):
            return 'LOW'
        
        return None
    
    @staticmethod
    def _check_market_structure(df: pd.DataFrame) -> Optional[str]:
        """Check for Higher Highs/Lows or Lower Highs/Lows"""
        if len(df) < 10:
            return None
        
        recent_high = df['High'].iloc[-1]
        prev_high = df['High'].iloc[-5:-1].max()
        
        recent_low = df['Low'].iloc[-1]
        prev_low = df['Low'].iloc[-5:-1].min()
        
        # Higher High + Higher Low = BULLISH
        if recent_high > prev_high and recent_low > prev_low:
            return 'HH/HL - BULLISH'
        
        # Lower High + Lower Low = BEARISH
        if recent_high < prev_high and recent_low < prev_low:
            return 'LH/LL - BEARISH'
        
        return None
    
    @staticmethod
    def _check_momentum(df: pd.DataFrame) -> Optional[str]:
        """Check price momentum"""
        closes = df['Close'].tail(5).values
        
        if len(closes) < 2:
            return None
        
        momentum = closes[-1] - closes[0]
        momentum_pct = (momentum / closes[0]) * 100
        
        if abs(momentum_pct) > 0.5:
            return 'STRONG' if momentum_pct > 0 else 'DOWN'
        
        return None
    
    @staticmethod
    def _calculate_optimal_entry(df: pd.DataFrame, direction: str) -> float:
        """Calculate best entry price"""
        if direction == 'LONG':
            # Buy on recent low + 0.1%
            low = df['Low'].tail(5).min()
            return low * 1.001
        else:
            # Sell on recent high - 0.1%
            high = df['High'].tail(5).max()
            return high * 0.999
        
        return df['Close'].iloc[-1]
    
    @staticmethod
    def _calculate_risk_reward(df: pd.DataFrame, direction: str, 
                              entry: float) -> Tuple[float, float]:
        """Calculate stop loss and take profit (1:2 ratio)"""
        atr = LiveSetupScanner._calculate_atr(df)
        
        if direction == 'LONG':
            stop = entry - (atr * 1.5)
            tp = entry + (atr * 3)
        else:
            stop = entry + (atr * 1.5)
            tp = entry - (atr * 3)
        
        return stop, tp
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - np.roll(close, 1)),
                np.abs(low - np.roll(close, 1))
            )
        )
        
        return np.mean(tr[-period:])
    
    @staticmethod
    def _score_confluence(structures: Dict) -> float:
        """Score setup based on confluence factors"""
        base_score = 50.0
        factor_scores = {
            'FVG Present': 15,
            'Liquidity Pool': 10,
            'MS': 20,
            'Momentum: STRONG': 15,
            'Momentum: DOWN': 15
        }
        
        for factor in structures.get('factors', []):
            for key, score in factor_scores.items():
                if key in factor:
                    base_score += score
        
        return min(100, base_score)
    
    @staticmethod
    def _determine_severity(confidence: float) -> AlertSeverity:
        """Map confidence to severity"""
        if confidence >= 90:
            return AlertSeverity.CRITICAL
        elif confidence >= 80:
            return AlertSeverity.HIGH
        elif confidence >= 70:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW
    
    @staticmethod
    def _generate_notes(structures: Dict, score: float) -> str:
        """Generate analysis notes"""
        factors = ', '.join(structures.get('factors', []))
        return f"Confluence: {factors} | Confidence: {score:.1f}%"
    
    def get_alerts(self, severity: Optional[AlertSeverity] = None) -> List[MarketAlert]:
        """Get all alerts, optionally filtered by severity"""
        if severity:
            return [a for a in self.alerts if a.severity == severity]
        return self.alerts
    
    def export_alerts(self, filename: str = 'alerts.csv') -> None:
        """Export alerts to CSV"""
        if not self.alerts:
            print("No alerts to export")
            return
        
        df = pd.DataFrame([a.to_dict() for a in self.alerts])
        df.to_csv(filename, index=False)
        print(f"Exported {len(self.alerts)} alerts to {filename}")


class CorrelationMonitor:
    """Monitor correlations between assets for divergence trading"""
    
    @staticmethod
    def calculate_rolling_correlation(asset_a: pd.Series, asset_b: pd.Series,
                                     window: int = 20) -> np.ndarray:
        """Calculate rolling correlation between two assets"""
        return asset_a.rolling(window).corr(asset_b)
    
    @staticmethod
    def detect_correlation_break(corr_series: np.ndarray, 
                                threshold: float = 0.1) -> List[int]:
        """Detect when correlation breaks from historical level"""
        mean_corr = np.nanmean(corr_series)
        breaks = []
        
        for i in range(1, len(corr_series)):
            if not np.isnan(corr_series[i]):
                deviation = abs(corr_series[i] - mean_corr)
                if deviation > threshold:
                    breaks.append(i)
        
        return breaks


if __name__ == "__main__":
    print("Real-Time Market Scanner Module Loaded")
    print("\nFeatures:")
    print("✓ Multi-timeframe confluence detection")
    print("✓ Live setup scanning with confidence scoring")
    print("✓ Automatic alert generation")
    print("✓ Liquidity pool detection")
    print("✓ FVG + Market structure scanning")
    print("✓ Correlation monitoring for SMT divergence")
    print("\nImport: from live_scanner import LiveSetupScanner, MultiTimeframeAnalyzer")
