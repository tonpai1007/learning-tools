"""
PLC Ladder Logic Simulator
Simulates basic industrial PLC logic for training and portfolio projects.
"""

import time
import threading
from enum import Enum
from dataclasses import dataclass
from typing import List, Callable, Optional


class SignalState(Enum):
    OFF = 0
    ON = 1


@dataclass
class PLCInput:
    name: str
    state: SignalState = SignalState.OFF


@dataclass
class PLCOutput:
    name: str
    state: SignalState = SignalState.OFF


class PLCLadderRung:
    """Represents one rung of ladder logic."""
    
    def __init__(self, name: str):
        self.name = name
        self.inputs: List[Callable] = []
        self.output: Optional[Callable] = None
        self.enable_condition: Callable = lambda: True
    
    def add_input(self, condition: Callable) -> 'PLCLadderRung':
        self.inputs.append(condition)
        return self
    
    def set_output(self, output_func: Callable) -> 'PLCLadderRung':
        self.output = output_func
        return self
    
    def evaluate(self) -> bool:
        if not self.enable_condition():
            return False
        result = all(input_func() for input_func in self.inputs)
        if self.output and result:
            self.output(result)
        return result


class SimplePLC:
    """A simple PLC simulator for educational purposes."""
    
    def __init__(self, scan_time_ms: int = 100):
        self.scan_time = scan_time_ms / 1000.0
        self.inputs: dict[str, PLCInput] = {}
        self.outputs: dict[str, PLCOutput] = {}
        self.rungs: List[PLCLadderRung] = []
        self.running = False
        self.scan_count = 0
    
    def add_input(self, name: str, initial_state: SignalState = SignalState.OFF) -> PLCInput:
        inp = PLCInput(name=name, state=initial_state)
        self.inputs[name] = inp
        return inp
    
    def add_output(self, name: str, initial_state: SignalState = SignalState.OFF) -> PLCOutput:
        out = PLCOutput(name=name, state=initial_state)
        self.outputs[name] = out
        return out
    
    def set_input(self, name: str, state: SignalState):
        if name in self.inputs:
            self.inputs[name].state = state
    
    def get_output(self, name: str) -> Optional[SignalState]:
        if name in self.outputs:
            return self.outputs[name].state
        return None
    
    def add_rung(self, rung: PLCLadderRung):
        self.rungs.append(rung)
    
    def scan_cycle(self):
        """Execute one PLC scan cycle."""
        self.scan_count += 1
        for rung in self.outputs.values():
            # Reset outputs at start of scan (latch behavior)
            pass
        for rung in self.rungs:
            rung.evaluate()
    
    def run(self, cycles: int = 100, callback: Optional[Callable] = None):
        """Run PLC for specified number of scan cycles."""
        self.running = True
        for i in range(cycles):
            if not self.running:
                break
            self.scan_cycle()
            if callback:
                callback(self, i)
            time.sleep(self.scan_time)
        self.running = False
    
    def stop(self):
        self.running = False


def build_motor_control_plc() -> SimplePLC:
    """
    Build a motor start/stop control with run indicator.
    
    I0.0 = Start button (NO)
    I0.1 = Stop button (NC)
    I0.2 = Overload (NC)
    Q0.0 = Motor
    Q0.1 = Run indicator
    """
    plc = SimplePLC(scan_time_ms=50)
    
    # Add I/O
    start_btn = plc.add_input("I0.0_Start")
    stop_btn = plc.add_input("I0.1_Stop", initial_state=SignalState.ON)  # NC button
    overload = plc.add_input("I0.2_Overload", initial_state=SignalState.ON)  # NC
    motor = plc.add_output("Q0.0_Motor")
    indicator = plc.add_output("Q0.1_Run_Indicator")
    
    # Rung 1: Motor control (seal-in circuit)
    def motor_logic(result):
        motor.state = SignalState.ON if result else SignalState.OFF
        indicator.state = motor.state
    
    rung1 = PLCLadderRung("Motor_Control")
    rung1.add_input(lambda: start_btn.state == SignalState.ON)
    rung1.add_input(lambda: stop_btn.state == SignalState.ON)
    rung1.add_input(lambda: overload.state == SignalState.ON)
    rung1.set_output(motor_logic)
    plc.add_rung(rung1)
    
    return plc


def build_conveyor_plc() -> SimplePLC:
    """
    Build a conveyor system with counter and sensor logic.
    
    I0.0 = Start
    I0.1 = Stop
    I0.2 = Product sensor
    I0.3 = Counter reset
    C0 = Part counter (10 parts = batch complete)
    Q0.0 = Conveyor
    Q0.1 = Batch complete indicator
    """
    plc = SimplePLC(scan_time_ms=50)
    
    start = plc.add_input("I0.0_Start")
    stop = plc.add_input("I0.1_Stop", initial_state=SignalState.ON)
    sensor = plc.add_input("I0.2_Position_Sensor")
    reset = plc.add_input("I0.3_Counter_Reset")
    
    conveyor = plc.add_output("Q0.0_Conveyor")
    batch_done = plc.add_output("Q0.1_Batch_Complete")
    
    # Counter simulation
    counter = {"count": 0, "prev_sensor": SignalState.OFF}
    
    def conveyor_logic(result):
        conveyor.state = SignalState.ON if result else SignalState.OFF
    
    rung1 = PLCLadderRung("Conveyor_Control")
    rung1.add_input(lambda: start.state == SignalState.ON)
    rung1.add_input(lambda: stop.state == SignalState.ON)
    rung1.set_output(conveyor_logic)
    plc.add_rung(rung1)
    
    # Counter logic
    def counter_logic(_):
        # Rising edge detection on sensor
        if conveyor.state == SignalState.ON and sensor.state == SignalState.ON and counter["prev_sensor"] == SignalState.OFF:
            counter["count"] += 1
        counter["prev_sensor"] = sensor.state
        
        # Reset
        if reset.state == SignalState.ON:
            counter["count"] = 0
        
        # Batch complete at 10
        if counter["count"] >= 10:
            batch_done.state = SignalState.ON
        else:
            batch_done.state = SignalState.OFF
    
    rung2 = PLCLadderRung("Batch_Counter")
    rung2.add_input(lambda: True)  # Always execute
    rung2.set_output(counter_logic)
    plc.add_rung(rung2)
    
    return plc


def build_traffic_light_plc() -> SimplePLC:
    """
    Build a traffic light sequence controller.
    
    Sequence: Green (5s) -> Yellow (2s) -> Red (5s)
    """
    plc = SimplePLC(scan_time_ms=100)
    
    green = plc.add_output("Q0.0_Green")
    yellow = plc.add_output("Q0.1_Yellow")
    red = plc.add_output("Q0.2_Red")
    
    state = {"phase": 0, "timer": 0}
    
    def traffic_logic(_):
        state["timer"] += 1
        
        if state["phase"] == 0:  # Green
            green.state = SignalState.ON
            yellow.state = SignalState.OFF
            red.state = SignalState.OFF
            if state["timer"] >= 50:  # 5s
                state["phase"] = 1
                state["timer"] = 0
        elif state["phase"] == 1:  # Yellow
            green.state = SignalState.OFF
            yellow.state = SignalState.ON
            red.state = SignalState.OFF
            if state["timer"] >= 20:  # 2s
                state["phase"] = 2
                state["timer"] = 0
        elif state["phase"] == 2:  # Red
            green.state = SignalState.OFF
            yellow.state = SignalState.OFF
            red.state = SignalState.ON
            if state["timer"] >= 50:  # 5s
                state["phase"] = 0
                state["timer"] = 0
    
    rung = PLCLadderRung("Traffic_Sequence")
    rung.add_input(lambda: True)
    rung.set_output(traffic_logic)
    plc.add_rung(rung)
    
    return plc


def demo():
    """Run a quick demo of the motor control PLC."""
    plc = build_motor_control_plc()
    
    print("=== Motor Control PLC Demo ===")
    print(f"{'Scan':<6} {'Start':<8} {'Stop':<8} {'Motor':<8} {'Indicator'}")
    
    def status_callback(plc, i):
        start = plc.inputs["I0.0_Start"].state == SignalState.ON
        stop = plc.inputs["I0.1_Stop"].state == SignalState.ON
        motor = plc.outputs["Q0.0_Motor"].state == SignalState.ON
        indicator = plc.outputs["Q0.1_Run_Indicator"].state == SignalState.ON
        print(f"{i:<6} {str(start):<8} {str(stop):<8} {str(motor):<8} {str(indicator)}")
    
    # Press start button
    plc.set_input("I0.0_Start", SignalState.ON)
    plc.run(cycles=10, callback=status_callback)
    
    # Release start button (seal-in should keep motor running)
    plc.set_input("I0.0_Start", SignalState.OFF)
    plc.run(cycles=10, callback=status_callback)
    
    # Press stop button
    plc.set_input("I0.1_Stop", SignalState.OFF)  # NC button released = stop
    plc.run(cycles=10, callback=status_callback)
    
    print("\n=== Conveyor Counter Demo ===")
    conv = build_conveyor_plc()
    
    conv.set_input("I0.0_Start", SignalState.ON)
    
    print(f"{'Scan':<6} {'Conv':<8} {'Sensor':<8} {'Count':<8} {'Batch'}")
    
    def conv_callback(plc, i):
        conv_state = plc.outputs["Q0.0_Conveyor"].state == SignalState.ON
        sensor = plc.inputs["I0.2_Position_Sensor"].state == SignalState.ON
        batch = plc.outputs["Q0.1_Batch_Complete"].state == SignalState.ON
        # Simulate sensor pulses every 5 scans
        if i % 5 == 0 and i > 0 and i < 51:
            plc.set_input("I0.2_Position_Sensor", SignalState.ON)
        else:
            plc.set_input("I0.2_Position_Sensor", SignalState.OFF)
        print(f"{i:<6} {str(conv_state):<8} {str(sensor):<8} {str(plc.scan_count):<8} {str(batch)}")
    
    conv.run(cycles=60, callback=conv_callback)
    
    print("\n=== Traffic Light Demo ===")
    traffic = build_traffic_light_plc()
    
    print(f"{'Scan':<6} {'Green':<8} {'Yellow':<8} {'Red'}")
    
    def traffic_callback(plc, i):
        g = plc.outputs["Q0.0_Green"].state == SignalState.ON
        y = plc.outputs["Q0.1_Yellow"].state == SignalState.ON
        r = plc.outputs["Q0.2_Red"].state == SignalState.ON
        print(f"{i:<6} {str(g):<8} {str(y):<8} {str(r)}")
    
    traffic.run(cycles=80, callback=traffic_callback)


if __name__ == "__main__":
    demo()
