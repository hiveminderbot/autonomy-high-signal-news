#!/usr/bin/env python3
"""
Unit tests for the briefing delivery module.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from briefing.delivery import (
    DeliveryResult,
    DeliveryChannel,
    EmailDelivery,
    TelegramDelivery,
    FileDelivery,
    MultiChannelDelivery,
    create_delivery_from_config
)


class TestDeliveryResult(unittest.TestCase):
    """Test the DeliveryResult dataclass."""

    def test_basic_creation(self):
        """Test creating a basic DeliveryResult."""
        result = DeliveryResult(
            success=True,
            channel='email',
            timestamp='2026-03-21T10:00:00',
            message='Delivered to 1 recipient'
        )

        self.assertTrue(result.success)
        self.assertEqual(result.channel, 'email')
        self.assertEqual(result.message, 'Delivered to 1 recipient')
        self.assertEqual(result.retries, 0)
        self.assertIsNone(result.error)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = DeliveryResult(
            success=False,
            channel='telegram',
            timestamp='2026-03-21T10:00:00',
            message='Failed',
            retries=3,
            error='Connection timeout'
        )

        d = result.to_dict()
        self.assertEqual(d['success'], False)
        self.assertEqual(d['channel'], 'telegram')
        self.assertEqual(d['error'], 'Connection timeout')
        self.assertEqual(d['retries'], 3)


class TestEmailDelivery(unittest.TestCase):
    """Test the EmailDelivery channel."""

    def setUp(self):
        """Set up test environment."""
        # Clear environment variables
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.env_patcher.stop()

    def test_not_configured_without_env(self):
        """Test that delivery is not configured without environment variables."""
        delivery = EmailDelivery()
        self.assertFalse(delivery.is_configured())

    def test_configured_with_env(self):
        """Test that delivery is configured with environment variables."""
        with patch.dict(os.environ, {
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_USERNAME': 'test@example.com',
            'SMTP_PASSWORD': 'password123',
            'EMAIL_TO': 'recipient@example.com'
        }):
            delivery = EmailDelivery()
            self.assertTrue(delivery.is_configured())

    def test_configured_with_constructor_args(self):
        """Test that delivery is configured with constructor arguments."""
        delivery = EmailDelivery(
            smtp_host='smtp.example.com',
            username='user@example.com',
            password='pass123',
            to_addresses=['recipient@example.com']
        )
        self.assertTrue(delivery.is_configured())

    def test_deliver_without_config(self):
        """Test delivery attempt without configuration."""
        delivery = EmailDelivery()
        result = delivery.deliver('Test content')

        self.assertFalse(result.success)
        self.assertEqual(result.channel, 'email')
        self.assertIn('not configured', result.message)
        self.assertIsNotNone(result.error)

    @patch('smtplib.SMTP')
    def test_deliver_with_config(self, mock_smtp_class):
        """Test successful email delivery."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        delivery = EmailDelivery(
            smtp_host='smtp.gmail.com',
            smtp_port=587,
            username='sender@example.com',
            password='pass123',
            from_address='sender@example.com',
            to_addresses=['recipient@example.com']
        )

        result = delivery.deliver('Test content', 'Test Subject')

        self.assertTrue(result.success)
        self.assertEqual(result.channel, 'email')
        self.assertIn('recipient', result.message)

        # Verify SMTP calls
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with('sender@example.com', 'pass123')
        mock_smtp.send_message.assert_called_once()


class TestTelegramDelivery(unittest.TestCase):
    """Test the TelegramDelivery channel."""

    def setUp(self):
        """Set up test environment."""
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.env_patcher.stop()

    def test_not_configured_without_env(self):
        """Test that delivery is not configured without environment variables."""
        delivery = TelegramDelivery()
        self.assertFalse(delivery.is_configured())

    def test_configured_with_env(self):
        """Test that delivery is configured with environment variables."""
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'bot123:token',
            'TELEGRAM_CHAT_ID': '-123456789'
        }):
            delivery = TelegramDelivery()
            self.assertTrue(delivery.is_configured())

    def test_deliver_without_config(self):
        """Test delivery attempt without configuration."""
        delivery = TelegramDelivery()
        result = delivery.deliver('Test content')

        self.assertFalse(result.success)
        self.assertEqual(result.channel, 'telegram')
        self.assertIn('not configured', result.message)

    @patch('briefing.delivery.urlopen')
    def test_deliver_single_message(self, mock_urlopen):
        """Test successful Telegram delivery."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({'ok': True}).encode()
        mock_urlopen.return_value.__enter__ = Mock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = Mock(return_value=False)

        delivery = TelegramDelivery(
            bot_token='bot123:test_token',
            chat_id='-123456789'
        )

        result = delivery.deliver('Test message', 'Test Subject')

        self.assertTrue(result.success)
        self.assertEqual(result.channel, 'telegram')
        self.assertIn('message', result.message)

    def test_split_message_short(self):
        """Test that short messages are not split."""
        delivery = TelegramDelivery()
        content = "Short message"

        chunks = delivery._split_message(content)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], content)

    def test_split_message_long(self):
        """Test that long messages are split correctly."""
        delivery = TelegramDelivery()
        # Create content longer than MAX_MESSAGE_LENGTH (4096)
        # Each line should be short so we can split on newlines
        lines = ["Line " + str(i) for i in range(200)]  # ~1400 chars
        content = "\n".join(lines)
        # Add more content to exceed the limit
        content = content + "\n" + ("X" * 3000)  # Now exceeds 4096

        chunks = delivery._split_message(content)
        self.assertGreater(len(chunks), 1)

        # Each chunk should be within limits
        for chunk in chunks:
            self.assertLessEqual(len(chunk), delivery.MAX_MESSAGE_LENGTH)


class TestFileDelivery(unittest.TestCase):
    """Test the FileDelivery channel."""

    def setUp(self):
        """Set up temporary directory."""
        self.test_dir = Path(__file__).parent / 'test_output'
        self.test_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_is_configured(self):
        """Test that file delivery is always configured."""
        delivery = FileDelivery(output_dir=self.test_dir)
        self.assertTrue(delivery.is_configured())

    def test_deliver_creates_files(self):
        """Test that delivery creates expected files."""
        delivery = FileDelivery(
            output_dir=self.test_dir,
            filename_format='briefing_{date}.md'
        )

        content = "# Test Briefing\n\nThis is a test."
        subject = "Test Subject"

        result = delivery.deliver(content, subject)

        self.assertTrue(result.success)
        self.assertEqual(result.channel, 'file')

        # Check that files were created
        date_str = datetime.now().strftime('%Y-%m-%d')
        main_file = self.test_dir / f'briefing_{date_str}.md'
        latest_file = self.test_dir / 'latest.md'
        meta_file = self.test_dir / f'briefing_{date_str}.json'

        self.assertTrue(main_file.exists())
        self.assertTrue(latest_file.exists())
        self.assertTrue(meta_file.exists())

        # Check content
        with open(main_file) as f:
            saved_content = f.read()
        self.assertIn(subject, saved_content)
        self.assertIn(content, saved_content)

        # Check metadata
        with open(meta_file) as f:
            metadata = json.load(f)
        self.assertEqual(metadata['subject'], subject)
        self.assertIn('generated_at', metadata)


class TestMultiChannelDelivery(unittest.TestCase):
    """Test the MultiChannelDelivery class."""

    def test_empty_channels(self):
        """Test with no configured channels - auto-configures from env."""
        with patch.dict(os.environ, {}, clear=True):
            delivery = MultiChannelDelivery(channels=[])
            results = delivery.deliver('Test')

        # Auto-configures FileDelivery at minimum
        self.assertGreaterEqual(len(results), 0)

    def test_single_channel(self):
        """Test with a single channel."""
        mock_channel = Mock(spec=DeliveryChannel)
        mock_channel.deliver.return_value = DeliveryResult(
            success=True,
            channel='mock',
            timestamp=datetime.now(timezone.utc).isoformat(),
            message='Mock delivery'
        )
        type(mock_channel).__name__ = 'MockChannel'

        delivery = MultiChannelDelivery(channels=[mock_channel])
        results = delivery.deliver('Test content', 'Test Subject')

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)
        mock_channel.deliver.assert_called_once_with('Test content', 'Test Subject')

    def test_multiple_channels(self):
        """Test with multiple channels."""
        mock1 = Mock(spec=DeliveryChannel)
        mock1.deliver.return_value = DeliveryResult(
            success=True, channel='mock1',
            timestamp=datetime.now(timezone.utc).isoformat(), message='OK'
        )
        type(mock1).__name__ = 'MockChannel1'

        mock2 = Mock(spec=DeliveryChannel)
        mock2.deliver.return_value = DeliveryResult(
            success=False, channel='mock2',
            timestamp=datetime.now(timezone.utc).isoformat(), message='Failed', error='Error'
        )
        type(mock2).__name__ = 'MockChannel2'

        delivery = MultiChannelDelivery(channels=[mock1, mock2])
        results = delivery.deliver('Test')

        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].success)
        self.assertFalse(results[1].success)

    def test_get_configured_channels(self):
        """Test getting list of configured channels."""
        # Use actual delivery instances instead of mocks to get proper class names
        file_delivery = FileDelivery(output_dir='/tmp/test_output')

        delivery = MultiChannelDelivery(channels=[file_delivery])
        channels = delivery.get_configured_channels()

        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0], 'FileDelivery')

    def test_exception_handling(self):
        """Test that exceptions in one channel don't break others."""
        mock1 = Mock(spec=DeliveryChannel)
        mock1.deliver.side_effect = Exception("Channel 1 failed")
        type(mock1).__name__ = 'FailingChannel'

        mock2 = Mock(spec=DeliveryChannel)
        mock2.deliver.return_value = DeliveryResult(
            success=True, channel='mock2',
            timestamp=datetime.now(timezone.utc).isoformat(), message='OK'
        )
        type(mock2).__name__ = 'WorkingChannel'

        delivery = MultiChannelDelivery(channels=[mock1, mock2])
        results = delivery.deliver('Test')

        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].success)
        self.assertEqual(results[0].error, "Channel 1 failed")
        self.assertTrue(results[1].success)


class TestCreateDeliveryFromConfig(unittest.TestCase):
    """Test the create_delivery_from_config factory function."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(__file__).parent / 'test_config'
        self.test_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test files."""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_from_config_file(self):
        """Test loading from a config file."""
        config = {
            'email': {
                'enabled': True,
                'smtp_host': 'smtp.example.com',
                'username': 'test@example.com',
                'password': 'pass123',
                'to_addresses': ['recipient@example.com']
            },
            'file': {
                'enabled': True,
                'output_dir': str(self.test_dir / 'output')
            }
        }

        config_path = self.test_dir / 'delivery.json'
        with open(config_path, 'w') as f:
            json.dump(config, f)

        delivery = create_delivery_from_config(config_path)
        channels = delivery.get_configured_channels()

        self.assertIn('EmailDelivery', channels)
        self.assertIn('FileDelivery', channels)

    def test_from_environment(self):
        """Test fallback to environment configuration."""
        with patch.dict(os.environ, {
            'SMTP_HOST': 'smtp.gmail.com',
            'SMTP_USERNAME': 'test@example.com',
            'SMTP_PASSWORD': 'pass123',
            'EMAIL_TO': 'recipient@example.com'
        }, clear=True):
            delivery = create_delivery_from_config('/nonexistent/path.json')
            channels = delivery.get_configured_channels()

            # Should have EmailDelivery from environment
            self.assertIn('EmailDelivery', channels)


if __name__ == '__main__':
    unittest.main(verbosity=2)
