# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2008-2026 Andrew Ziem.
#
# This work is licensed under the terms of the GNU GPL, version 3 or
# later.  See the COPYING file in the top-level directory.


"""
Test case for module GtkShim
"""

import ctypes
import os
import unittest
from unittest import mock

from tests import common
from bleachbit.GtkShim import (
    _check_display_available,
    _is_macos_gui_launch_context,
    _build_error_html,
    _handle_gtk_import_error,
    _show_windows_error_dialog,
    path_has_lib_or_bin,
)


class PathHasLibOrBinTestCase(unittest.TestCase):
    """Test path_has_lib_or_bin() detection logic."""

    def test_path_has_lib_or_bin(self):
        """Test path_has_lib_or_bin() with various paths."""
        tests = [
            # (path, expected_result)
            # Standalone 'bin' directory triggers detection
            (r'C:\bin', 'bin'),
            (r'C:\bin\xlib', 'bin'),
            (r'C:\libx\bin', 'bin'),
            (r'C:\bin\bin', 'bin'),
            (r'C:\Users\username\Downloads\bin\BleachBit-Portable', 'bin'),
            # Standalone 'lib' directory triggers detection
            (r'C:\lib', 'lib'),
            (r'C:\lib\xbin', 'lib'),
            (r'C:\binx\lib', 'lib'),
            (r'C:\lib\lib', 'lib'),
            (r'C:\Users\username\Downloads\lib\BleachBit-Portable', 'lib'),
            (r'C:\ProgramData\chocolatey\lib\bleachbit.portable\BleachBit-Portable', 'lib'),
            # Detection is case-insensitive
            (r'C:\Users\BIN\app', 'bin'),
            (r'C:\Users\Lib\app', 'lib'),
            # 'binx' is not 'bin'
            (r'C:\Users\username\Downloads\binx\BleachBit-Portable', None),
            # 'xbin' is not 'bin'
            (r'C:\Users\username\Downloads\xbin\BleachBit-Portable', None),
            # 'libfoo' is not 'lib'
            (r'C:\ProgramData\libfoo\app', None),
            # Normal portable path without lib or bin
            (r'C:\Users\username\Downloads\BleachBit-5.0.0-portable\BleachBit-Portable', None),
            # Empty path returns None
            ('', None),
            # 'lib' or 'bin' embedded in longer names should not match
            (r'C:\calibre\library\app', None),
            (r'C:\cabinet\app', None),
        ]
        case_functions = (
            lambda x: x.lower(),
            lambda x: x.upper(),
            lambda x: x.title(),
            lambda x: x.title().swapcase(),
        )
        for path, expected in tests:
            with self.subTest(path=path, expected=expected):
                joined = os.path.join(path, 'bleachbit.exe')
                for func in case_functions:
                    self.assertEqual(path_has_lib_or_bin(
                        func(joined)), expected)


class BuildErrorHtmlTestCase(unittest.TestCase):
    """Tests for _build_error_html()."""

    def test_unknown_error_includes_traceback_and_sysinfo(self):
        """Unknown-error HTML must include traceback and system information."""
        html = _build_error_html(
            RuntimeError('something broke'),
            traceback_text='Traceback (most recent call last):...',
        )
        self.assertIn('Error: something broke', html)
        self.assertIn('Traceback (most recent call last):...', html)
        self.assertIn('System information:\n', html)
        self.assertIn('textarea', html)
        self.assertIn('Copy to clipboard', html)
        self.assertIn("function copyBugReport()", html)
        self.assertIn('get-help', html)
        self.assertEqual(html.count('<textarea'), 1)
        self.assertEqual(html.count('<pre>'), 0)

    def test_unknown_error_escapes_html_in_error_message(self):
        """Error message containing HTML special chars must be escaped."""
        html = _build_error_html(
            RuntimeError('<script>alert(1)</script>'),
        )
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_html_structure(self):
        """Output must be valid minimal HTML with required elements."""
        html = _build_error_html(
            Exception('test'),
        )
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('<html', html)
        self.assertIn('BleachBit cannot start', html)


class CheckDisplayAvailableTestCase(unittest.TestCase):
    """Tests for _check_display_available()."""

    def test_windows_always_available(self):
        """Windows should report a display even without DISPLAY variables."""
        with mock.patch('os.name', 'nt'), \
                mock.patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}, clear=False):
            ok, reason = _check_display_available()
            self.assertTrue(ok)
            self.assertIsNone(reason)

    def test_macos_bundle_launch_without_display_vars_is_available(self):
        """macOS bundle launches should not require DISPLAY/WAYLAND_DISPLAY."""
        with mock.patch('os.name', 'posix'), \
                mock.patch('sys.platform', 'darwin'), \
                mock.patch.dict(
                    os.environ,
                    {
                        'DISPLAY': '',
                        'WAYLAND_DISPLAY': '',
                        '__CFBundleIdentifier': 'org.bleachbit.BleachBit',
                    },
                    clear=False,
                ):
            ok, reason = _check_display_available()
            self.assertTrue(ok)
            self.assertIsNone(reason)

    def test_macos_console_launch_is_unavailable(self):
        """macOS console launches should fail gracefully before GTK import."""
        with mock.patch('os.name', 'posix'), \
                mock.patch('sys.platform', 'darwin'), \
                mock.patch('sys.executable', '/opt/homebrew/bin/python3'), \
                mock.patch.dict(
                    os.environ,
                    {
                        'DISPLAY': '',
                        'WAYLAND_DISPLAY': '',
                        '__CFBundleIdentifier': 'com.apple.Terminal',
                    },
                    clear=False,
                ):
            ok, reason = _check_display_available()
            self.assertFalse(ok)
            self.assertIn('BleachBit app bundle', reason)
    def test_posix_without_display_vars_is_unavailable(self):
        """Other POSIX platforms should require DISPLAY/WAYLAND_DISPLAY."""
        with mock.patch('os.name', 'posix'), \
                mock.patch('sys.platform', 'linux'), \
                mock.patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}, clear=False):
            ok, reason = _check_display_available()
            self.assertFalse(ok)
            self.assertIn('No DISPLAY or WAYLAND_DISPLAY', reason)


class ShowWindowsErrorDialogTestCase(unittest.TestCase):
    """Tests for _show_windows_error_dialog() (non-Windows stubs)."""

    @common.skipUnlessWindows
    def test_yes_writes_html_file(self):
        """Selecting Yes must write the HTML file and open the browser."""
        with mock.patch.object(
            ctypes.windll.user32, 'MessageBoxW', return_value=6
        ), mock.patch('webbrowser.open') as mock_open:
            _show_windows_error_dialog('BleachBit', '<html>test</html>')
            mock_open.assert_called_once()
            html_path = mock_open.call_args[0][0].replace('file:///', '')
            with open(html_path, encoding='utf-8') as f:
                self.assertIn('test', f.read())

    @common.skipUnlessWindows
    def test_no_does_not_write_file(self):
        """Selecting No must not open the browser."""
        with mock.patch.object(
            ctypes.windll.user32, 'MessageBoxW', return_value=7
        ), mock.patch('webbrowser.open') as mock_open:
            _show_windows_error_dialog('BleachBit', '<html/>')
            mock_open.assert_not_called()


class HandleGtkImportErrorTestCase(unittest.TestCase):
    """Tests for _handle_gtk_import_error()."""

    @common.skipIfWindows
    def test_noop_on_non_windows(self):
        """Must do nothing on non-Windows platforms."""
        with mock.patch('bleachbit.GtkShim._show_windows_error_dialog') as m:
            _handle_gtk_import_error(ValueError('test'))
            m.assert_not_called()

    @common.skipUnlessWindows
    def test_unknown_error_includes_traceback_in_html(self):
        """Unknown errors must produce HTML with traceback section."""
        with mock.patch('bleachbit.GtkShim._show_windows_error_dialog') as m, \
                mock.patch('sys.frozen', True, create=True), \
                mock.patch('sys.executable', r'C:\Users\user\Apps\BleachBit\bleachbit.exe'):
            try:
                raise RuntimeError('something broke')
            except RuntimeError as e:
                _handle_gtk_import_error(e)
            m.assert_called_once()
            _title, html = m.call_args[0]
            self.assertIn('Traceback', html)
            self.assertIn('System information', html)


class MacGuiLaunchContextTestCase(unittest.TestCase):
    """Tests for _is_macos_gui_launch_context()."""

    def test_false_outside_macos(self):
        """Non-macOS platforms must not be treated as macOS app launches."""
        with mock.patch('sys.platform', 'linux'):
            self.assertFalse(_is_macos_gui_launch_context())

    def test_true_for_matching_bundle_identifier(self):
        """The BleachBit bundle identifier should enable macOS GUI startup."""
        with mock.patch('sys.platform', 'darwin'), \
                mock.patch.dict(
                    os.environ,
                    {'__CFBundleIdentifier': 'org.bleachbit.BleachBit'},
                    clear=False,
                ):
            self.assertTrue(_is_macos_gui_launch_context())

    def test_true_for_frozen_app_bundle_without_bundle_identifier(self):
        """Frozen app bundles should work even if the env bundle id is absent."""
        with mock.patch('sys.platform', 'darwin'), \
                mock.patch('sys.executable', '/Applications/BleachBit.app/Contents/MacOS/BleachBit'), \
                mock.patch('sys.frozen', True, create=True), \
                mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(_is_macos_gui_launch_context())

    def test_false_for_direct_python_launch(self):
        """Direct interpreter launches should not be treated as app bundles."""
        with mock.patch('sys.platform', 'darwin'), \
                mock.patch('sys.executable', '/opt/homebrew/bin/python3'), \
                mock.patch.dict(
                    os.environ,
                    {'__CFBundleIdentifier': 'com.apple.Terminal'},
                    clear=False,
                ):
            self.assertFalse(_is_macos_gui_launch_context())


if __name__ == '__main__':
    unittest.main()
