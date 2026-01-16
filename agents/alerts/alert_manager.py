"""
Agent #21: Alert Manager

Monitors trading signals and sends beautiful terminal alerts.
Tracks alert history and manages notification thresholds.

Capabilities:
1. send_alert - Display formatted alert in terminal
2. check_thresholds - Monitor signals and trigger alerts
3. get_alert_history - Retrieve past alerts
4. configure_alerts - Set alert preferences
"""

import sys
import os
import smtplib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email import policy
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from sqlalchemy import select, and_

from agents.base_agent import BaseAgent
from shared.data_models import AgentMetadata, AgentCapability

# Load environment variables
load_dotenv()


class AlertManager(BaseAgent):
    """Manages alerts and notifications for trading signals."""
    
    def __init__(self):
        self.console = Console()
        super().__init__()
    
    def get_metadata(self) -> AgentMetadata:
        """Return agent metadata."""
        return AgentMetadata(
            agent_id="alert_manager",
            name="Alert Manager",
            description="Send beautiful terminal alerts for trading signals",
            version="1.0.0",
            category="alerts",
            enabled=True,
            capabilities=[
                AgentCapability(
                    name="send_alert",
                    description="Display formatted alert in terminal",
                    parameters={
                        "alert_type": "str (SIGNAL, WARNING, INFO)",
                        "symbol": "str",
                        "action": "str (BUY, SELL, HOLD)",
                        "confidence": "int (0-100)",
                        "message": "str",
                        "details": "dict (optional)"
                    }
                ),
                AgentCapability(
                    name="check_thresholds",
                    description="Check if signal meets alert thresholds",
                    parameters={
                        "signals": "List[dict]",
                        "min_confidence": "int (default: 75 for BUY, 25 for SELL)"
                    }
                ),
                AgentCapability(
                    name="get_alert_history",
                    description="Get recent alerts",
                    parameters={
                        "hours": "int (default: 24)",
                        "alert_type": "str (optional)"
                    }
                ),
                AgentCapability(
                    name="configure_alerts",
                    description="Configure alert preferences",
                    parameters={
                        "buy_threshold": "int (0-100)",
                        "sell_threshold": "int (0-100)",
                        "enabled": "bool"
                    }
                ),
                AgentCapability(
                    name="send_email_alert",
                    description="Send trading signal alert via email",
                    parameters={
                        "symbol": "str",
                        "action": "str (BUY, SELL, HOLD)",
                        "confidence": "int (0-100)",
                        "details": "dict",
                        "to_email": "str (optional, uses default from config)"
                    }
                )
            ],
            dependencies=[]
        )
    
    async def initialize(self):
        """Initialize the agent."""
        # Default alert configuration
        self.alert_config = {
            "buy_threshold": 75,      # Alert on STRONG_BUY (75+)
            "sell_threshold": 25,     # Alert on STRONG_SELL (25-)
            "enabled": True
        }
        
        # Email configuration from environment variables
        self.email_config = {
            "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "smtp_user": os.getenv("SMTP_USER", ""),
            "smtp_password": os.getenv("SMTP_PASSWORD", ""),
            "from_email": os.getenv("FROM_EMAIL", ""),
            "to_email": os.getenv("TO_EMAIL", "krsna.nandula@gmail.com"),
            "email_enabled": os.getenv("EMAIL_ALERTS_ENABLED", "true").lower() == "true"
        }
        
        # Alert history (in-memory for now)
        self.alert_history: List[Dict[str, Any]] = []
        
        # Log email configuration status
        if self.email_config["email_enabled"]:
            if self.email_config["smtp_user"] and self.email_config["smtp_password"]:
                logger.info(f"Email alerts enabled. Will send to: {self.email_config['to_email']}")
            else:
                logger.warning("Email alerts enabled but SMTP credentials not configured")
        else:
            logger.info("Email alerts disabled")
        
        logger.info("alert_manager initialized")
    
    async def _send_alert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a formatted alert to terminal.
        
        Args:
            params: {
                "alert_type": str,
                "symbol": str,
                "action": str,
                "confidence": int,
                "message": str,
                "details": dict (optional)
            }
        """
        alert_type = params.get("alert_type", "INFO")
        symbol = params.get("symbol", "")
        action = params.get("action", "")
        confidence = params.get("confidence", 0)
        message = params.get("message", "")
        details = params.get("details", {})
        
        # Determine color scheme based on action
        if action in ["STRONG_BUY", "BUY"]:
            color = "green"
            emoji = "📈" if action == "STRONG_BUY" else "🟢"
        elif action in ["STRONG_SELL", "SELL"]:
            color = "red"
            emoji = "📉" if action == "STRONG_SELL" else "🔴"
        else:
            color = "yellow"
            emoji = "⚪"
        
        # Create title
        title = f"{emoji} {alert_type}: {symbol}"
        
        # Create main message
        main_text = Text()
        main_text.append(f"{action}\n", style=f"bold {color}")
        main_text.append(f"Confidence: {confidence}/100\n", style="cyan")
        main_text.append(f"\n{message}", style="white")
        
        # Add details table if provided
        if details:
            table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")
            
            for key, value in details.items():
                table.add_row(key, str(value))
            
            # Display alert with table
            self.console.print()
            self.console.print(Panel(
                main_text,
                title=title,
                border_style=color,
                box=box.DOUBLE
            ))
            self.console.print(table)
            self.console.print()
        else:
            # Display alert without table
            self.console.print()
            self.console.print(Panel(
                main_text,
                title=title,
                border_style=color,
                box=box.DOUBLE
            ))
            self.console.print()
        
        # Store in history
        alert_record = {
            "timestamp": datetime.now().isoformat(),
            "alert_type": alert_type,
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "message": message,
            "details": details
        }
        self.alert_history.append(alert_record)
        
        return {
            "success": True,
            "alert_sent": True,
            "timestamp": alert_record["timestamp"]
        }
    
    async def _check_thresholds(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check signals against alert thresholds.
        
        Args:
            params: {
                "signals": List[dict],
                "min_confidence": int (optional)
            }
        """
        signals = params.get("signals", [])
        
        if not self.alert_config["enabled"]:
            return {
                "success": True,
                "alerts_triggered": 0,
                "message": "Alerts are disabled"
            }
        
        buy_threshold = self.alert_config["buy_threshold"]
        sell_threshold = self.alert_config["sell_threshold"]
        
        triggered_alerts = []
        
        for signal in signals:
            symbol = signal.get("symbol", "")
            action = signal.get("action", "")
            confidence = signal.get("confidence", 0)
            
            should_alert = False
            alert_message = ""
            
            # Check BUY signals
            if action in ["STRONG_BUY", "BUY"] and confidence >= buy_threshold:
                should_alert = True
                alert_message = f"Strong buy signal detected! Consider buying {symbol}."
            
            # Check SELL signals
            elif action in ["STRONG_SELL", "SELL"] and confidence <= sell_threshold:
                should_alert = True
                alert_message = f"Strong sell signal detected! Consider selling {symbol}."
            
            if should_alert:
                # Extract details from signal
                details = {
                    "Technical Score": f"{signal.get('technical_score', 0)}/50",
                    "Macro Score": f"{signal.get('macro_score', 0)}/50",
                    "Position Size": f"{signal.get('position_size_pct', 0)}%"
                }
                
                if signal.get('trade_plan'):
                    plan = signal['trade_plan']
                    if 'exit_optimal' in plan:
                        details["Exit Price"] = f"${plan['exit_optimal']:.2f}"
                        details["Re-entry"] = f"${plan['reentry_target']:.2f}"
                    elif 'entry_optimal' in plan:
                        details["Entry Price"] = f"${plan['entry_optimal']:.2f}"
                        details["Stop Loss"] = f"${plan['stop_loss']:.2f}"
                        details["Target"] = f"${plan['take_profit_1']:.2f}"
                
                # Send alert
                await self._send_alert({
                    "alert_type": "SIGNAL",
                    "symbol": symbol,
                    "action": action,
                    "confidence": confidence,
                    "message": alert_message,
                    "details": details
                })
                
                triggered_alerts.append({
                    "symbol": symbol,
                    "action": action,
                    "confidence": confidence
                })
        
        return {
            "success": True,
            "alerts_triggered": len(triggered_alerts),
            "alerts": triggered_alerts
        }
    
    async def _get_alert_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get recent alert history.
        
        Args:
            params: {
                "hours": int (default: 24),
                "alert_type": str (optional)
            }
        """
        hours = params.get("hours", 24)
        alert_type = params.get("alert_type")
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filter alerts
        filtered_alerts = []
        for alert in self.alert_history:
            alert_time = datetime.fromisoformat(alert["timestamp"])
            
            if alert_time >= cutoff_time:
                if alert_type is None or alert["alert_type"] == alert_type:
                    filtered_alerts.append(alert)
        
        return {
            "success": True,
            "count": len(filtered_alerts),
            "alerts": filtered_alerts,
            "timeframe_hours": hours
        }
    
    async def _configure_alerts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure alert preferences.
        
        Args:
            params: {
                "buy_threshold": int (optional),
                "sell_threshold": int (optional),
                "enabled": bool (optional)
            }
        """
        if "buy_threshold" in params:
            self.alert_config["buy_threshold"] = params["buy_threshold"]
        
        if "sell_threshold" in params:
            self.alert_config["sell_threshold"] = params["sell_threshold"]
        
        if "enabled" in params:
            self.alert_config["enabled"] = params["enabled"]
        
        return {
            "success": True,
            "config": self.alert_config.copy()
        }
    
    async def _send_email_alert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send trading signal alert via email.
        
        Args:
            params: {
                "symbol": str,
                "action": str,
                "confidence": int,
                "details": dict,
                "to_email": str (optional)
            }
        """
        # Check if email is enabled and configured
        if not self.email_config["email_enabled"]:
            return {
                "success": False,
                "error": "Email alerts are disabled"
            }
        
        if not self.email_config["smtp_user"] or not self.email_config["smtp_password"]:
            logger.warning("Email alert failed: SMTP credentials not configured")
            return {
                "success": False,
                "error": "SMTP credentials not configured"
            }
        
        symbol = params.get("symbol", "")
        action = params.get("action", "")
        confidence = params.get("confidence", 0)
        details = params.get("details", {})
        to_email = params.get("to_email", self.email_config["to_email"])
        
        # Determine action color based on action (no emoji in email)
        if action in ["STRONG_BUY", "BUY"]:
            action_color = "#28a745"  # Green
            subject_prefix = "[BUY]"
            alert_symbol = "▲"  # Up arrow
        elif action in ["STRONG_SELL", "SELL"]:
            action_color = "#dc3545"  # Red
            subject_prefix = "[SELL]"
            alert_symbol = "▼"  # Down arrow
        else:
            action_color = "#ffc107"  # Yellow
            subject_prefix = "[HOLD]"
            alert_symbol = "■"  # Square
        
        # Create subject without emoji (for email compatibility)
        subject = f"{subject_prefix} Trading Alert: {symbol} - {action}"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {action_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; }}
                .content {{ background-color: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; }}
                .signal {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .confidence {{ font-size: 18px; color: #17a2b8; margin: 10px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: white; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
                th {{ background-color: #e9ecef; font-weight: bold; }}
                .footer {{ margin-top: 20px; padding: 15px; text-align: center; color: #6c757d; font-size: 12px; }}
                .timestamp {{ color: #6c757d; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{alert_symbol} Trading Signal Alert</h1>
                    <div class="signal">{symbol}</div>
                </div>
                <div class="content">
                    <div class="signal" style="color: {action_color};">{action}</div>
                    <div class="confidence">Confidence: {confidence}/100</div>
                    <div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
        """
        
        # Add details table if provided
        if details:
            html_body += """
                    <table>
                        <thead>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            for key, value in details.items():
                html_body += f"""
                            <tr>
                                <td>{key}</td>
                                <td><strong>{value}</strong></td>
                            </tr>
                """
            
            html_body += """
                        </tbody>
                    </table>
            """
        
        html_body += """
                </div>
                <div class="footer">
                    <p>This is an automated trading alert from your 100AC Gold/Silver Trading System</p>
                    <p>Please review all signals carefully before making trading decisions</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create email message with UTF-8 encoding and proper policy
        message = MIMEMultipart("alternative", policy=policy.SMTPUTF8)
        message["Subject"] = subject  # Plain text subject, no emoji
        message["From"] = self.email_config["from_email"] or self.email_config["smtp_user"]
        message["To"] = to_email
        
        # Add HTML content with UTF-8 encoding (emoji in HTML body is fine)
        html_part = MIMEText(html_body, "html", "utf-8")
        message.attach(html_part)
        
        # Send email
        try:
            # Convert message to bytes first to catch encoding issues early
            try:
                message_bytes = message.as_bytes()
            except UnicodeEncodeError as e:
                logger.error(f"Failed to convert message to bytes: {e}")
                raise
            
            with smtplib.SMTP(self.email_config["smtp_server"], self.email_config["smtp_port"]) as server:
                server.set_debuglevel(0)  # Disable debug output
                server.starttls()
                # Ensure credentials are strings
                smtp_user = str(self.email_config["smtp_user"])
                smtp_password = str(self.email_config["smtp_password"])
                server.login(smtp_user, smtp_password)
                # Use sendmail with as_bytes for proper UTF-8 encoding
                server.sendmail(
                    from_addr=self.email_config["from_email"] or smtp_user,
                    to_addrs=[to_email],
                    msg=message_bytes
                )
            
            logger.info(f"Email alert sent to {to_email}: {symbol} - {action} ({confidence}/100)")
            
            return {
                "success": True,
                "to_email": to_email,
                "symbol": symbol,
                "action": action
            }
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {str(e)}")
            return {
                "success": False,
                "error": f"Authentication failed: {str(e)}"
            }
        except UnicodeEncodeError as e:
            logger.error(f"Unicode encoding error: {str(e)}")
            logger.error(f"Subject: '{subject}'")
            logger.error(f"Symbol: '{symbol}'")
            logger.error(f"Action: '{action}'")
            logger.error(f"HTML body length: {len(html_body)}")
            # Find the problematic character
            try:
                subject.encode('ascii')
            except UnicodeEncodeError as e2:
                logger.error(f"Subject encoding failed: {e2}")
            return {
                "success": False,
                "error": f"Encoding error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_combined_email_alert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a combined email alert with multiple trading signals.
        
        Args:
            params: {
                "signals": List[dict] - List of signal dictionaries
                "to_email": str (optional)
            }
        """
        # Check if email is enabled and configured
        if not self.email_config["email_enabled"]:
            return {
                "success": False,
                "error": "Email alerts are disabled"
            }
        
        if not self.email_config["smtp_user"] or not self.email_config["smtp_password"]:
            logger.warning("Email alert failed: SMTP credentials not configured")
            return {
                "success": False,
                "error": "SMTP credentials not configured"
            }
        
        signals = params.get("signals", [])
        if not signals:
            return {
                "success": False,
                "error": "No signals provided"
            }
        
        to_email = params.get("to_email", self.email_config["to_email"])
        
        # Determine overall sentiment
        buy_count = sum(1 for s in signals if s.get('action') in ['BUY', 'STRONG_BUY'])
        sell_count = sum(1 for s in signals if s.get('action') in ['SELL', 'STRONG_SELL'])
        
        if buy_count > sell_count:
            subject_prefix = "[BUY]"
            header_color = "#28a745"
            alert_symbol = "▲"
        elif sell_count > buy_count:
            subject_prefix = "[SELL]"
            header_color = "#dc3545"
            alert_symbol = "▼"
        else:
            subject_prefix = "[MIXED]"
            header_color = "#6c757d"
            alert_symbol = "■"
        
        # Create subject
        subject = f"{subject_prefix} Gold/Silver Trading Alerts - {len(signals)} Signal(s)"
        
        # Build HTML email with all signals
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {header_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; }}
                .content {{ background-color: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; }}
                .signal-card {{ background: white; margin: 15px 0; padding: 15px; border-radius: 6px; border-left: 4px solid #dee2e6; }}
                .signal-card.buy {{ border-left-color: #28a745; }}
                .signal-card.sell {{ border-left-color: #dc3545; }}
                .signal-card.hold {{ border-left-color: #ffc107; }}
                .signal-title {{ font-size: 20px; font-weight: bold; margin-bottom: 10px; }}
                .confidence {{ font-size: 16px; color: #17a2b8; margin: 5px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #dee2e6; font-size: 14px; }}
                th {{ background-color: #e9ecef; font-weight: bold; }}
                .footer {{ margin-top: 20px; padding: 15px; text-align: center; color: #6c757d; font-size: 12px; }}
                .timestamp {{ color: #6c757d; font-size: 14px; margin-top: 15px; }}
                .summary {{ background: white; padding: 15px; margin-bottom: 20px; border-radius: 6px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{alert_symbol} Gold/Silver Trading Alerts</h1>
                    <p style="margin: 5px 0; font-size: 18px;">{len(signals)} Signal(s) Generated</p>
                </div>
                <div class="content">
                    <div class="summary">
                        <strong>Summary:</strong> {buy_count} BUY, {sell_count} SELL, {len(signals) - buy_count - sell_count} HOLD
                    </div>
        """
        
        # Add each signal as a card
        for signal in signals:
            symbol = signal.get('symbol', '')
            action = signal.get('action', '')
            confidence = signal.get('confidence', 0)
            
            # Determine card class
            if action in ['BUY', 'STRONG_BUY']:
                card_class = 'buy'
                action_color = '#28a745'
            elif action in ['SELL', 'STRONG_SELL']:
                card_class = 'sell'
                action_color = '#dc3545'
            else:
                card_class = 'hold'
                action_color = '#ffc107'
            
            html_body += f"""
                    <div class="signal-card {card_class}">
                        <div class="signal-title" style="color: {action_color};">{symbol}: {action}</div>
                        <div class="confidence">Confidence: {confidence}/100</div>
                        <table>
                            <tr>
                                <th>Metric</th>
                                <th>Value</th>
                            </tr>
                            <tr>
                                <td>Technical Score</td>
                                <td><strong>{signal.get('technical_score', 0)}/50</strong></td>
                            </tr>
                            <tr>
                                <td>Macro Score</td>
                                <td><strong>{signal.get('macro_score', 0)}/50</strong></td>
                            </tr>
                            <tr>
                                <td>Position Size</td>
                                <td><strong>{signal.get('position_size_pct', 0)}%</strong></td>
                            </tr>
                            <tr>
                                <td>Entry Price</td>
                                <td><strong>${signal.get('trade_plan', {}).get('entry_optimal', 0):.2f}</strong></td>
                            </tr>
                            <tr>
                                <td>Stop Loss</td>
                                <td><strong>${signal.get('trade_plan', {}).get('stop_loss', 0):.2f}</strong></td>
                            </tr>
                            <tr>
                                <td>Target</td>
                                <td><strong>${signal.get('trade_plan', {}).get('take_profit_1', 0):.2f}</strong></td>
                            </tr>
                            <tr>
                                <td>Risk/Reward</td>
                                <td><strong>1:{signal.get('trade_plan', {}).get('risk_reward_ratio', 0):.1f}</strong></td>
                            </tr>
                        </table>
                    </div>
            """
        
        # Close HTML
        html_body += f"""
                    <div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
                </div>
                <div class="footer">
                    <p>This is an automated trading alert from your 100AC Gold/Silver Trading System</p>
                    <p>Please review all signals carefully before making trading decisions</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create email message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.email_config["from_email"] or self.email_config["smtp_user"]
        message["To"] = to_email
        
        # Add HTML content
        html_part = MIMEText(html_body, "html", "utf-8")
        message.attach(html_part)
        
        # Send email
        try:
            # Convert message to bytes first
            try:
                message_bytes = message.as_bytes()
            except UnicodeEncodeError as e:
                logger.error(f"Failed to convert message to bytes: {e}")
                raise
            
            with smtplib.SMTP(self.email_config["smtp_server"], self.email_config["smtp_port"]) as server:
                server.set_debuglevel(0)
                server.starttls()
                smtp_user = str(self.email_config["smtp_user"])
                smtp_password = str(self.email_config["smtp_password"])
                server.login(smtp_user, smtp_password)
                server.sendmail(
                    from_addr=self.email_config["from_email"] or smtp_user,
                    to_addrs=[to_email],
                    msg=message_bytes
                )
            
            logger.info(f"Combined email alert sent to {to_email}: {len(signals)} signals")
            
            return {
                "success": True,
                "to_email": to_email,
                "signal_count": len(signals)
            }
            
        except Exception as e:
            logger.error(f"Failed to send combined email alert: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_request(self, message: Any) -> Dict[str, Any]:
        """
        Process incoming alert requests.
        
        Args:
            message: Message with action and parameters
            
        Returns:
            Result dictionary
        """
        # This is handled by BaseAgent's capability routing
        # Just return empty dict as BaseAgent will route to proper methods
        return {}
    
    async def shutdown(self):
        """Cleanup on shutdown."""
        logger.info("alert_manager shutdown complete")


# Test harness
if __name__ == "__main__":
    import asyncio
    
    async def test_alerts():
        """Test alert manager."""
        manager = AlertManager()
        await manager.initialize()
        await manager.start()
        
        try:
            # Test STRONG_BUY alert
            print("\n=== Testing STRONG_BUY Alert ===")
            await manager._send_alert({
                "alert_type": "SIGNAL",
                "symbol": "GLD",
                "action": "STRONG_BUY",
                "confidence": 85,
                "message": "Excellent buying opportunity! All technical and macro indicators are aligned.",
                "details": {
                    "Technical Score": "45/50",
                    "Macro Score": "40/50",
                    "Position Size": "25%",
                    "Entry Price": "$400.50",
                    "Stop Loss": "$390.00",
                    "Target": "$430.00",
                    "Risk/Reward": "1:3"
                }
            })
            
            # Test STRONG_SELL alert
            print("\n=== Testing STRONG_SELL Alert ===")
            await manager._send_alert({
                "alert_type": "SIGNAL",
                "symbol": "SLV",
                "action": "STRONG_SELL",
                "confidence": 20,
                "message": "Overbought conditions detected. Consider taking profits.",
                "details": {
                    "Technical Score": "15/50",
                    "Macro Score": "5/50",
                    "Position Size": "-100%",
                    "Exit Price": "$82.49",
                    "Re-entry": "$70.82",
                    "Monthly RSI": "95.5"
                }
            })
            
            # Test threshold checking
            print("\n=== Testing Threshold Check ===")
            test_signals = [
                {
                    "symbol": "GLD",
                    "action": "STRONG_BUY",
                    "confidence": 85,
                    "technical_score": 45,
                    "macro_score": 40,
                    "position_size_pct": 25,
                    "trade_plan": {
                        "entry_optimal": 400.50,
                        "stop_loss": 390.00,
                        "take_profit_1": 430.00
                    }
                },
                {
                    "symbol": "SLV",
                    "action": "HOLD",
                    "confidence": 50,
                    "technical_score": 25,
                    "macro_score": 25,
                    "position_size_pct": 0
                }
            ]
            
            result = await manager._check_thresholds({"signals": test_signals})
            print(f"\nThreshold check result: {result['alerts_triggered']} alerts triggered")
            
            # Test alert history
            print("\n=== Testing Alert History ===")
            history = await manager._get_alert_history({"hours": 1})
            print(f"Found {history['count']} alerts in last hour")
            
        finally:
            await manager.stop()
            await manager.shutdown()
    
    asyncio.run(test_alerts())
