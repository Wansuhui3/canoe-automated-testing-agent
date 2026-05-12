"""
CANoe COM API Interface

Provides Python interface to Vector CANoe via COM automation,
enabling programmatic control of simulation, measurement, and data capture.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CANoeConfig:
    """CANoe simulation configuration."""
    canoe_cfg_path: str          # Path to .cfg file
    bus_type: str = "CAN"       # Bus type: CAN, LIN, FlexRay
    channel: int = 1            # Channel number
    baud_rate: int = 500000     # Baud rate
    log_file: Optional[str] = None  # Log file path


@dataclass
class SimulationResult:
    """Result of a CANoe simulation run."""
    success: bool
    duration_ms: int
    messages_sent: int
    messages_received: int
    errors: list[str]
    log_path: Optional[str] = None


class CANoeInterface:
    """
    Interface to Vector CANoe via COM automation (Windows only).

    Provides methods to:
    - Open/close CANoe configurations
    - Start/stop measurement
    - Send/receive CAN messages
    - Read signal values
    - Capture bus data for verification

    Note: Requires CANoe installed and pywin32 package.
    On non-Windows or without CANoe, operates in simulation mode.
    """

    def __init__(self, config: Optional[CANoeConfig] = None) -> None:
        """
        Initialize the CANoe interface.

        Args:
            config: CANoe configuration settings
        """
        self._config = config
        self._canoe_app = None
        self._measurement = None
        self._bus = None
        self._is_connected = False
        self._is_measuring = False
        self._simulation_mode = False

    def connect(self) -> bool:
        """
        Connect to CANoe application via COM.

        Returns:
            True if connected successfully
        """
        try:
            import win32com.client
            self._canoe_app = win32com.client.Dispatch("CANoe.Application")
            self._is_connected = True
            logger.info("Connected to CANoe via COM")
            return True
        except ImportError:
            logger.warning("pywin32 not available, switching to simulation mode")
            self._simulation_mode = True
            self._is_connected = True
            return True
        except Exception as e:
            logger.warning(f"Cannot connect to CANoe: {e}, switching to simulation mode")
            self._simulation_mode = True
            self._is_connected = True
            return True

    def open_configuration(self, cfg_path: Optional[str] = None) -> bool:
        """
        Open a CANoe configuration file.

        Args:
            cfg_path: Path to .cfg file (uses config default if None)

        Returns:
            True if opened successfully
        """
        path = cfg_path or (self._config.canoe_cfg_path if self._config else None)
        if not path:
            logger.error("No configuration path specified")
            return False

        if self._simulation_mode:
            logger.info(f"[SIM] Would open configuration: {path}")
            return True

        try:
            self._canoe_app.Open(path)
            logger.info(f"Opened CANoe configuration: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open configuration: {e}")
            return False

    def start_measurement(self) -> bool:
        """Start CANoe measurement."""
        if self._simulation_mode:
            logger.info("[SIM] Measurement started")
            self._is_measuring = True
            return True

        try:
            self._measurement = self._canoe_app.Measurement
            self._measurement.Start()
            self._is_measuring = True
            logger.info("CANoe measurement started")
            return True
        except Exception as e:
            logger.error(f"Failed to start measurement: {e}")
            return False

    def stop_measurement(self) -> bool:
        """Stop CANoe measurement."""
        if self._simulation_mode:
            logger.info("[SIM] Measurement stopped")
            self._is_measuring = False
            return True

        try:
            if self._measurement:
                self._measurement.Stop()
                self._is_measuring = False
                logger.info("CANoe measurement stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop measurement: {e}")
            return False

    def send_can_message(self, message_id: int, data: list[int], dlc: Optional[int] = None) -> bool:
        """
        Send a CAN message on the bus.

        Args:
            message_id: CAN message ID
            data: List of byte values (0-255)
            dlc: Data Length Code (defaults to len(data))
        """
        if dlc is None:
            dlc = len(data)

        if self._simulation_mode:
            data_hex = " ".join(f"{b:02X}" for b in data)
            logger.info(f"[SIM] TX: ID=0x{message_id:X}, DLC={dlc}, Data=[{data_hex}]")
            return True

        # Real CANoe COM API call would go here
        logger.warning("Real CANoe message sending not yet implemented")
        return False

    def read_signal_value(self, message_name: str, signal_name: str) -> Optional[float]:
        """
        Read a signal value from the CANoe simulation.

        Args:
            message_name: CAN message name
            signal_name: Signal name

        Returns:
            Signal physical value, or None if not available
        """
        if self._simulation_mode:
            logger.info(f"[SIM] Read: {message_name}.{signal_name} = 0.0")
            return 0.0

        try:
            bus = self._canoe_app.GetBus(self._config.channel if self._config else 1)
            signal = bus.GetSignal(message_name, signal_name)
            return signal.Value
        except Exception as e:
            logger.error(f"Failed to read signal: {e}")
            return None

    def disconnect(self) -> None:
        """Disconnect from CANoe."""
        if self._is_measuring:
            self.stop_measurement()
        self._is_connected = False
        self._canoe_app = None
        logger.info("Disconnected from CANoe")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_measuring(self) -> bool:
        return self._is_measuring

    @property
    def is_simulation_mode(self) -> bool:
        return self._simulation_mode
