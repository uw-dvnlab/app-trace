from abc import ABC, abstractmethod
from typing import List, Dict, Any

class SignalProcessor(ABC):
    name = "base"
    description = "Base processor"

    @classmethod
    def get_parameters(cls) -> List[Dict[str, Any]]:
        """
        Return a list of parameters for the processor.
        Each parameter is a dict with:
        - name: internal name
        - label: display name
        - type: 'int', 'float', 'bool', 'enum'
        - default: default value
        - min: min value (for numbers)
        - max: max value (for numbers)
        - step: step value (for numbers)
        - suffix: unit suffix (optional)
        """
        return []

    @abstractmethod
    def process(self, data, sampling_rate, **kwargs):
        """
        Process the signal data.
        
        Args:
            data: numpy array of signal values
            sampling_rate: sampling frequency in Hz
            **kwargs: parameter values
            
        Returns:
            processed data
        """
        pass