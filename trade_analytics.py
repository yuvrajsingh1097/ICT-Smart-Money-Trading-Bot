"""
Advanced Trade Analytics & Reporting Module
Comprehensive trade analysis, drawdown analysis, monthly returns heatmap
Export professional PDF reports from backtest results
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json


class TradeAnalytics:
    """Detailed analysis of individual trades"""
    
    def __init__(self, trades_df: pd.DataFrame):
        self.trades = trades_df.copy()
        self.metrics = {}
        self.analyze()
    
    def analyze(self) -> None:
        """Run complete trade analysis"""
        if len(self.trades) == 0:
            return
        
        # Basic metrics
        self.metrics['total_trades'] = len(self.trades)
        self.metrics['winning_trades'] = len(self.trades[self.trades['PnL'] > 0])
        self.metrics['losing_trades'] = len(self.trades[self.trades['PnL'] < 0])
        self.metrics['breakeven_trades'] = len(self.trades[self.trades['PnL'] == 0])
        
        # Win rate
        if len(self.trades) > 0:
            self.metrics['win_rate'] = (self.metrics['winning_trades'] / len(self.trades)) * 100
        
        # Profitability
        self.metrics['total_pnl'] = self.trades['PnL'].sum()
        self.metrics['avg_pnl_per_trade'] = self.trades['PnL'].mean()
        self.metrics['std_pnl'] = self.trades['PnL'].std()
        
        # Winning vs losing trades
        if self.metrics['winning_trades'] > 0:
            self.metrics['avg_win'] = self.trades[self.trades['PnL'] > 0]['PnL'].mean()
            self.metrics['max_win'] = self.trades[self.trades['PnL'] > 0]['PnL'].max()
        
        if self.metrics['losing_trades'] > 0:
            self.metrics['avg_loss'] = self.trades[self.trades['PnL'] < 0]['PnL'].mean()
            self.metrics['max_loss'] = self.trades[self.trades['PnL'] < 0]['PnL'].min()
        
        # Risk-reward ratio
        if self.metrics['losing_trades'] > 0 and self.metrics['winning_trades'] > 0:
            self.metrics['profit_factor'] = abs(
                (self.metrics['avg_win'] * self.metrics['winning_trades']) /
                (self.metrics['avg_loss'] * self.metrics['losing_trades'])
            )
        
        # Trade duration
        self.trades['Duration'] = self.trades['ExitBar'] - self.trades['EntryBar']
        self.metrics['avg_winning_duration'] = self.trades[
            self.trades['PnL'] > 0]['Duration'].mean() if self.metrics['winning_trades'] > 0 else 0
        self.metrics['avg_losing_duration'] = self.trades[
            self.trades['PnL'] < 0]['Duration'].mean() if self.metrics['losing_trades'] > 0 else 0
        
        # Consecutive wins/losses
        self.metrics['max_consecutive_wins'] = self._max_consecutive(self.trades['PnL'] > 0)
        self.metrics['max_consecutive_losses'] = self._max_consecutive(self.trades['PnL'] < 0)
    
    @staticmethod
    def _max_consecutive(condition_series: pd.Series) -> int:
        """Find longest streak of True values"""
        if len(condition_series) == 0:
            return 0
        
        max_streak = 0
        current_streak = 0
        
        for val in condition_series:
            if val:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def get_trade_quality_score(self) -> Dict:
        """Calculate trade quality metrics"""
        if len(self.trades) == 0:
            return {'error': 'No trades'}
        
        # Risk-reward quality
        rr_quality = 0
        if 'RRatio' in self.trades.columns:
            avg_rr = self.trades['RRatio'].mean()
            rr_quality = min(100, (avg_rr / 2.0) * 100)  # 1:2 is ideal
        
        # Win rate quality (55% is decent, 60% is good)
        wr_quality = (self.metrics['win_rate'] - 50) * 2  # Scale to 0-100
        wr_quality = max(0, min(100, wr_quality))
        
        # Consistency quality (lower std is better)
        if self.metrics['std_pnl'] > 0:
            consistency = 100 / (1 + (self.metrics['std_pnl'] / self.metrics['avg_pnl_per_trade']))
        else:
            consistency = 0
        
        overall_score = (rr_quality * 0.3 + wr_quality * 0.4 + consistency * 0.3)
        
        return {
            'overall_score': round(overall_score, 1),
            'rr_quality': round(rr_quality, 1),
            'win_rate_quality': round(wr_quality, 1),
            'consistency_quality': round(consistency, 1),
            'rating': self._score_to_rating(overall_score)
        }
    
    @staticmethod
    def _score_to_rating(score: float) -> str:
        """Convert score to rating"""
        if score >= 80:
            return 'EXCELLENT'
        elif score >= 70:
            return 'VERY GOOD'
        elif score >= 60:
            return 'GOOD'
        elif score >= 50:
            return 'FAIR'
        else:
            return 'POOR'
    
    def get_metrics_summary(self) -> str:
        """Get formatted metrics summary"""
        summary = []
        summary.append("\n" + "="*60)
        summary.append("TRADE ANALYTICS SUMMARY")
        summary.append("="*60)
        summary.append(f"Total Trades: {self.metrics.get('total_trades', 0)}")
        summary.append(f"Winning Trades: {self.metrics.get('winning_trades', 0)}")
        summary.append(f"Losing Trades: {self.metrics.get('losing_trades', 0)}")
        summary.append(f"Win Rate: {self.metrics.get('win_rate', 0):.2f}%")
        
        summary.append(f"\nProfitability:")
        summary.append(f"  Total P&L: ${self.metrics.get('total_pnl', 0):.2f}")
        summary.append(f"  Avg P&L/Trade: ${self.metrics.get('avg_pnl_per_trade', 0):.2f}")
        
        if 'avg_win' in self.metrics:
            summary.append(f"  Avg Win: ${self.metrics['avg_win']:.2f}")
            summary.append(f"  Max Win: ${self.metrics.get('max_win', 0):.2f}")
        
        if 'avg_loss' in self.metrics:
            summary.append(f"  Avg Loss: ${self.metrics['avg_loss']:.2f}")
            summary.append(f"  Max Loss: ${self.metrics.get('max_loss', 0):.2f}")
        
        if 'profit_factor' in self.metrics:
            summary.append(f"  Profit Factor: {self.metrics['profit_factor']:.2f}")
        
        summary.append(f"\nConsecutive Streaks:")
        summary.append(f"  Max Win Streak: {self.metrics.get('max_consecutive_wins', 0)}")
        summary.append(f"  Max Loss Streak: {self.metrics.get('max_consecutive_losses', 0)}")
        
        return "\n".join(summary)


class EquityCurveAnalytics:
    """Analyze equity curve and drawdowns"""
    
    def __init__(self, equity_series: pd.Series):
        self.equity = equity_series.values
        self.peaks = self._calculate_peaks()
        self.drawdowns = self._calculate_drawdowns()
        self.metrics = self._calculate_metrics()
    
    def _calculate_peaks(self) -> np.ndarray:
        """Calculate running maximum (peak equity)"""
        peaks = np.zeros_like(self.equity)
        peak = self.equity[0]
        
        for i, val in enumerate(self.equity):
            if val > peak:
                peak = val
            peaks[i] = peak
        
        return peaks
    
    def _calculate_drawdowns(self) -> np.ndarray:
        """Calculate drawdown at each point"""
        drawdowns = np.zeros_like(self.equity)
        
        for i in range(len(self.equity)):
            if self.peaks[i] > 0:
                drawdowns[i] = (self.equity[i] - self.peaks[i]) / self.peaks[i]
        
        return drawdowns
    
    def _calculate_metrics(self) -> Dict:
        """Calculate drawdown metrics"""
        metrics = {}
        
        # Maximum drawdown
        metrics['max_drawdown'] = np.min(self.drawdowns)
        metrics['max_drawdown_pct'] = metrics['max_drawdown'] * 100
        
        # Average drawdown
        metrics['avg_drawdown'] = np.mean(self.drawdowns[self.drawdowns < 0])
        metrics['avg_drawdown_pct'] = metrics['avg_drawdown'] * 100
        
        # Drawdown duration (bars)
        drawdown_bars = []
        current_dd = 0
        for dd in self.drawdowns:
            if dd < 0:
                current_dd += 1
            else:
                if current_dd > 0:
                    drawdown_bars.append(current_dd)
                current_dd = 0
        
        if drawdown_bars:
            metrics['max_drawdown_duration'] = max(drawdown_bars)
            metrics['avg_drawdown_duration'] = np.mean(drawdown_bars)
        else:
            metrics['max_drawdown_duration'] = 0
            metrics['avg_drawdown_duration'] = 0
        
        # Recovery factor
        total_gain = self.equity[-1] - self.equity[0]
        if metrics['max_drawdown'] != 0:
            metrics['recovery_factor'] = total_gain / abs(metrics['max_drawdown'] * self.peaks[0])
        else:
            metrics['recovery_factor'] = np.inf
        
        return metrics
    
    def get_drawdown_summary(self) -> str:
        """Get formatted drawdown summary"""
        summary = []
        summary.append("\n" + "="*60)
        summary.append("DRAWDOWN ANALYSIS")
        summary.append("="*60)
        summary.append(f"Max Drawdown: {self.metrics['max_drawdown_pct']:.2f}%")
        summary.append(f"Avg Drawdown: {self.metrics['avg_drawdown_pct']:.2f}%")
        summary.append(f"Max DD Duration: {self.metrics['max_drawdown_duration']:.0f} bars")
        summary.append(f"Avg DD Duration: {self.metrics['avg_drawdown_duration']:.0f} bars")
        summary.append(f"Recovery Factor: {self.metrics['recovery_factor']:.2f}x")
        
        return "\n".join(summary)


class MonthlyReturnsAnalyzer:
    """Analyze monthly return patterns"""
    
    def __init__(self, trades_df: pd.DataFrame, start_date: datetime = None):
        self.trades = trades_df.copy()
        self.start_date = start_date or datetime(2023, 1, 1)
        self.monthly_returns = {}
        self.analyze()
    
    def analyze(self) -> None:
        """Calculate monthly returns"""
        if 'ExitDate' not in self.trades.columns:
            return
        
        self.trades['Month'] = pd.to_datetime(
            self.trades.get('ExitDate', self.start_date)
        ).dt.to_period('M')
        
        monthly_pnl = self.trades.groupby('Month')['PnL'].agg(['sum', 'count'])
        
        for month, row in monthly_pnl.iterrows():
            self.monthly_returns[str(month)] = {
                'pnl': row['sum'],
                'trades': int(row['count'])
            }
    
    def get_monthly_heatmap_data(self) -> Dict:
        """Prepare data for monthly heatmap visualization"""
        heatmap_data = {}
        
        for month_str, data in self.monthly_returns.items():
            try:
                month_obj = pd.Period(month_str, freq='M')
                year = month_obj.year
                month = month_obj.month
                
                if year not in heatmap_data:
                    heatmap_data[year] = {}
                
                heatmap_data[year][month] = data['pnl']
            except:
                pass
        
        return heatmap_data
    
    def get_monthly_summary(self) -> str:
        """Get formatted monthly summary"""
        summary = []
        summary.append("\n" + "="*60)
        summary.append("MONTHLY RETURNS")
        summary.append("="*60)
        
        for month_str in sorted(self.monthly_returns.keys()):
            data = self.monthly_returns[month_str]
            summary.append(f"{month_str}: ${data['pnl']:>10.2f} ({int(data['trades'])} trades)")
        
        return "\n".join(summary)


class PerformanceReport:
    """Generate comprehensive performance report"""
    
    def __init__(self, backtest_results: Dict):
        self.results = backtest_results
        self.trade_analytics = None
        self.equity_analytics = None
        self.monthly_analyzer = None
        
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize all analytics modules"""
        if 'trades' in self.results:
            trades_df = pd.DataFrame(self.results['trades'])
            self.trade_analytics = TradeAnalytics(trades_df)
        
        if 'equity_curve' in self.results:
            equity_series = pd.Series(self.results['equity_curve'])
            self.equity_analytics = EquityCurveAnalytics(equity_series)
        
        if 'trades' in self.results:
            trades_df = pd.DataFrame(self.results['trades'])
            self.monthly_analyzer = MonthlyReturnsAnalyzer(trades_df)
    
    def generate_full_report(self) -> str:
        """Generate complete text report"""
        report = []
        
        report.append("\n" + "█"*60)
        report.append("█ ICT TRADING SYSTEM - PERFORMANCE REPORT")
        report.append("█"*60)
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # System metrics
        if 'system_metrics' in self.results:
            report.append("\n" + "="*60)
            report.append("SYSTEM METRICS")
            report.append("="*60)
            for key, val in self.results['system_metrics'].items():
                report.append(f"{key}: {val}")
        
        # Trade analytics
        if self.trade_analytics:
            report.append(self.trade_analytics.get_metrics_summary())
            quality = self.trade_analytics.get_trade_quality_score()
            report.append(f"\nTrade Quality Score: {quality.get('overall_score', 0)}/100")
            report.append(f"Rating: {quality.get('rating', 'N/A')}")
        
        # Equity analytics
        if self.equity_analytics:
            report.append(self.equity_analytics.get_drawdown_summary())
        
        # Monthly returns
        if self.monthly_analyzer:
            report.append(self.monthly_analyzer.get_monthly_summary())
        
        report.append("\n" + "="*60)
        
        return "\n".join(report)
    
    def export_report(self, filename: str) -> None:
        """Export report to text file"""
        with open(filename, 'w') as f:
            f.write(self.generate_full_report())
        print(f"Report exported to {filename}")
    
    def export_json(self, filename: str) -> None:
        """Export metrics as JSON"""
        export_data = {
            'trade_analytics': self.trade_analytics.metrics if self.trade_analytics else {},
            'equity_analytics': self.equity_analytics.metrics if self.equity_analytics else {},
            'monthly_returns': self.monthly_analyzer.monthly_returns if self.monthly_analyzer else {}
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        print(f"JSON metrics exported to {filename}")


if __name__ == "__main__":
    print("Advanced Analytics Module Loaded")
    print("\nFeatures:")
    print("✓ Trade-by-trade analysis")
    print("✓ Drawdown analysis with recovery metrics")
    print("✓ Monthly returns tracking")
    print("✓ Trade quality scoring")
    print("✓ Equity curve analytics")
    print("✓ Professional report generation")
    print("\nImport: from trade_analytics import TradeAnalytics, EquityCurveAnalytics, PerformanceReport")
