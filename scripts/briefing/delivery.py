#!/usr/bin/env python3
"""
Briefing Delivery Module - Phase 4

Handles delivery of generated briefings via multiple channels:
- Email (SMTP)
- Telegram Bot
- File output (for static sites, archiving)

All delivery methods support retry logic and error handling.
"""

import json
import logging
import os
import smtplib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Union
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    """Result of a delivery attempt."""
    success: bool
    channel: str
    timestamp: str
    message: str
    retries: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'channel': self.channel,
            'timestamp': self.timestamp,
            'message': self.message,
            'retries': self.retries,
            'error': self.error
        }


class DeliveryChannel(ABC):
    """Abstract base class for delivery channels."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    @abstractmethod
    def deliver(self, content: str, subject: Optional[str] = None) -> DeliveryResult:
        """Deliver content via this channel."""
        pass

    def _retry_wrapper(self, deliver_fn, content: str, subject: Optional[str] = None) -> DeliveryResult:
        """Wrapper to add retry logic to delivery."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = deliver_fn(content, subject)
                if result.success:
                    result.retries = 0
                    return result
                last_error = result.error
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Delivery attempt {attempt + 1} failed: {e}")

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff

        return DeliveryResult(
            success=False,
            channel=self.__class__.__name__,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message="Delivery failed after max retries",
            retries=self.max_retries,
            error=last_error
        )


class EmailDelivery(DeliveryChannel):
    """Deliver briefings via SMTP email."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_address: Optional[str] = None,
        to_addresses: Optional[list[str]] = None,
        use_tls: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)

        # Load from environment if not provided
        self.smtp_host = smtp_host or os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))
        self.username = username or os.getenv('SMTP_USERNAME')
        self.password = password or os.getenv('SMTP_PASSWORD')
        self.from_address = from_address or os.getenv('EMAIL_FROM') or self.username
        self.to_addresses = to_addresses or os.getenv('EMAIL_TO', '').split(',')
        self.use_tls = use_tls

        # Filter empty addresses
        self.to_addresses = [addr.strip() for addr in self.to_addresses if addr.strip()]

    def is_configured(self) -> bool:
        """Check if email delivery is properly configured."""
        return all([
            self.smtp_host,
            self.username,
            self.password,
            self.from_address,
            self.to_addresses
        ])

    def deliver(self, content: str, subject: Optional[str] = None) -> DeliveryResult:
        """Deliver briefing via email."""
        if not self.is_configured():
            return DeliveryResult(
                success=False,
                channel='email',
                timestamp=datetime.now(timezone.utc).isoformat(),
                message="Email delivery not configured",
                error="Missing required configuration (SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_TO)"
            )

        def _send_email(content: str, subject: Optional[str]) -> DeliveryResult:
            subject = subject or f"Daily Briefing - {datetime.now().strftime('%Y-%m-%d')}"

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_address
            msg['To'] = ', '.join(self.to_addresses)

            # Attach both plain text and HTML versions
            msg.attach(MIMEText(content, 'plain', 'utf-8'))

            # Try to extract HTML if content is markdown
            try:
                import markdown
                html_content = markdown.markdown(content, extensions=['extra', 'codehilite'])
                html_body = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                               line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
                        h1 {{ color: #333; border-bottom: 2px solid #eee; }}
                        h2 {{ color: #555; margin-top: 30px; }}
                        h3 {{ color: #666; }}
                        .emoji {{ font-size: 1.2em; }}
                        .tier-must-read {{ border-left: 4px solid #e74c3c; padding-left: 10px; }}
                        .tier-important {{ border-left: 4px solid #f39c12; padding-left: 10px; }}
                        .tier-contextual {{ border-left: 4px solid #3498db; padding-left: 10px; }}
                        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
                    </style>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
                """
                msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            except ImportError:
                pass  # Markdown not available, skip HTML version

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            return DeliveryResult(
                success=True,
                channel='email',
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=f"Delivered to {len(self.to_addresses)} recipient(s)"
            )

        return self._retry_wrapper(_send_email, content, subject)


class TelegramDelivery(DeliveryChannel):
    """Deliver briefings via Telegram Bot."""

    MAX_MESSAGE_LENGTH = 4096

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')

    def is_configured(self) -> bool:
        """Check if Telegram delivery is properly configured."""
        return bool(self.bot_token and self.chat_id)

    def _split_message(self, content: str) -> list[str]:
        """Split content into chunks that fit Telegram's message limit."""
        if len(content) <= self.MAX_MESSAGE_LENGTH:
            return [content]

        chunks = []
        current_chunk = ""

        for line in content.split('\n'):
            if len(current_chunk) + len(line) + 1 > self.MAX_MESSAGE_LENGTH:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def deliver(self, content: str, subject: Optional[str] = None) -> DeliveryResult:
        """Deliver briefing via Telegram."""
        if not self.is_configured():
            return DeliveryResult(
                success=False,
                channel='telegram',
                timestamp=datetime.now(timezone.utc).isoformat(),
                message="Telegram delivery not configured",
                error="Missing required configuration (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)"
            )

        def _send_telegram(content: str, subject: Optional[str]) -> DeliveryResult:
            # Prepend subject if provided
            if subject:
                content = f"**{subject}**\n\n{content}"

            # Escape markdown characters
            content = content.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')

            chunks = self._split_message(content)
            sent_count = 0

            for i, chunk in enumerate(chunks):
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'text': chunk,
                    'parse_mode': 'MarkdownV2',
                    'disable_web_page_preview': True
                }

                if i > 0:  # Add continuation indicator for split messages
                    payload['text'] = f"\\(continued {i+1}/{len(chunks)}\\)\\n\\n{chunk}"

                req = Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )

                try:
                    with urlopen(req, timeout=30) as response:
                        result = json.loads(response.read().decode('utf-8'))
                        if result.get('ok'):
                            sent_count += 1
                        else:
                            raise HTTPError(url, 400, result.get('description'), {}, None)
                except HTTPError as e:
                    # If markdown parsing fails, try without parse_mode
                    if 'can\'t parse entities' in str(e):
                        payload['parse_mode'] = None
                        payload['text'] = chunk.replace('\\*', '*').replace('\\_', '_').replace('\\`', '`')
                        req = Request(
                            url,
                            data=json.dumps(payload).encode('utf-8'),
                            headers={'Content-Type': 'application/json'},
                            method='POST'
                        )
                        with urlopen(req, timeout=30) as response:
                            result = json.loads(response.read().decode('utf-8'))
                            if result.get('ok'):
                                sent_count += 1
                            else:
                                raise
                    else:
                        raise

                # Small delay between chunks to avoid rate limiting
                if i < len(chunks) - 1:
                    time.sleep(0.5)

            return DeliveryResult(
                success=True,
                channel='telegram',
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=f"Delivered in {sent_count} message(s)"
            )

        return self._retry_wrapper(_send_telegram, content, subject)


class FileDelivery(DeliveryChannel):
    """Deliver briefings by writing to files (for archiving or static sites)."""

    def __init__(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        filename_format: str = "briefing_{date}.md",
        **kwargs
    ):
        super().__init__(**kwargs)

        self.output_dir = Path(output_dir or os.getenv('BRIEFING_OUTPUT_DIR', './output'))
        self.filename_format = filename_format

    def is_configured(self) -> bool:
        """Check if file delivery is properly configured."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    def deliver(self, content: str, subject: Optional[str] = None) -> DeliveryResult:
        """Deliver briefing by writing to file."""
        if not self.is_configured():
            return DeliveryResult(
                success=False,
                channel='file',
                timestamp=datetime.now(timezone.utc).isoformat(),
                message="File delivery not configured",
                error=f"Cannot write to output directory: {self.output_dir}"
            )

        def _write_file(content: str, subject: Optional[str]) -> DeliveryResult:
            date_str = datetime.now().strftime('%Y-%m-%d')
            filename = self.filename_format.format(date=date_str)
            filepath = self.output_dir / filename

            # Write main file
            with open(filepath, 'w', encoding='utf-8') as f:
                if subject:
                    f.write(f"# {subject}\n\n")
                f.write(content)

            # Also write to "latest.md" for easy access
            latest_path = self.output_dir / "latest.md"
            with open(latest_path, 'w', encoding='utf-8') as f:
                if subject:
                    f.write(f"# {subject}\n\n")
                f.write(content)

            # Write metadata JSON
            meta_path = self.output_dir / f"briefing_{date_str}.json"
            metadata = {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'subject': subject,
                'filename': filename,
                'size_bytes': len(content.encode('utf-8')),
                'line_count': len(content.split('\n'))
            }
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            return DeliveryResult(
                success=True,
                channel='file',
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=f"Written to {filepath} and {latest_path}"
            )

        return self._retry_wrapper(_write_file, content, subject)


class MultiChannelDelivery:
    """Deliver briefings via multiple channels simultaneously."""

    def __init__(self, channels: Optional[list[DeliveryChannel]] = None):
        self.channels = channels or []

        # Auto-configure from environment if no channels specified
        if not self.channels:
            email = EmailDelivery()
            if email.is_configured():
                self.channels.append(email)

            telegram = TelegramDelivery()
            if telegram.is_configured():
                self.channels.append(telegram)

            file_delivery = FileDelivery()
            if file_delivery.is_configured():
                self.channels.append(file_delivery)

    def deliver(self, content: str, subject: Optional[str] = None) -> list[DeliveryResult]:
        """Deliver to all configured channels."""
        results = []

        for channel in self.channels:
            try:
                result = channel.deliver(content, subject)
                results.append(result)

                if result.success:
                    logger.info(f"✓ Delivered via {result.channel}: {result.message}")
                else:
                    logger.error(f"✗ Failed to deliver via {result.channel}: {result.error}")

            except Exception as e:
                logger.exception(f"Unexpected error delivering via {channel.__class__.__name__}")
                results.append(DeliveryResult(
                    success=False,
                    channel=channel.__class__.__name__,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    message="Delivery failed with exception",
                    error=str(e)
                ))

        return results

    def get_configured_channels(self) -> list[str]:
        """Get list of configured channel names."""
        return [ch.__class__.__name__ for ch in self.channels]


def create_delivery_from_config(config_path: Optional[Union[str, Path]] = None) -> MultiChannelDelivery:
    """Create a MultiChannelDelivery instance from a config file or environment."""
    channels = []

    # Try to load from config file
    if config_path:
        config_path = Path(config_path)
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)

                if config.get('email', {}).get('enabled', False):
                    email_config = {k: v for k, v in config['email'].items() if k != 'enabled'}
                    channels.append(EmailDelivery(**email_config))

                if config.get('telegram', {}).get('enabled', False):
                    telegram_config = {k: v for k, v in config['telegram'].items() if k != 'enabled'}
                    channels.append(TelegramDelivery(**telegram_config))

                if config.get('file', {}).get('enabled', True):
                    file_config = {k: v for k, v in config['file'].items() if k != 'enabled'}
                    channels.append(FileDelivery(**file_config))

            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")

    # Fall back to environment-based configuration
    if not channels:
        return MultiChannelDelivery()

    return MultiChannelDelivery(channels)


if __name__ == "__main__":
    # Simple CLI for testing delivery
    import argparse

    parser = argparse.ArgumentParser(description='Test briefing delivery')
    parser.add_argument('--channel', choices=['email', 'telegram', 'file', 'all'], default='file',
                        help='Delivery channel to test')
    parser.add_argument('--content', default='This is a test briefing.',
                        help='Content to deliver')
    parser.add_argument('--subject', default='Test Briefing',
                        help='Subject line')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.channel == 'all':
        delivery = MultiChannelDelivery()
    elif args.channel == 'email':
        delivery = MultiChannelDelivery([EmailDelivery()])
    elif args.channel == 'telegram':
        delivery = MultiChannelDelivery([TelegramDelivery()])
    else:
        delivery = MultiChannelDelivery([FileDelivery()])

    results = delivery.deliver(args.content, args.subject)

    for result in results:
        status = "✓" if result.success else "✗"
        print(f"{status} {result.channel}: {result.message}")
        if result.error:
            print(f"  Error: {result.error}")
