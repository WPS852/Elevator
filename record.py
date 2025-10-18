#!/usr/bin/env python3
"""
电梯模拟数据记录器 - 集成版
继承算法类，在运行时记录数据
"""
import json
import time
from typing import Any, Dict, List
from pathlib import Path

from elevator_saga.client_examples.our_example import TestElevatorBusController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import SimulationEvent


class RecordingController(TestElevatorBusController):
    """带录制功能的电梯控制器"""
    
    def __init__(self):
        super().__init__()
        self.scenarios_data = []
        self.current_scenario_frames = []
        self.current_scenario_name = ""
        self.scenario_count = 0
        self.max_scenarios = 11
        
    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化时开始新场景的录制"""
        super().on_init(elevators, floors)
        
        # 开始新场景
        self.current_scenario_frames = []
        self.scenario_count += 1
        
        # 获取场景名称
        traffic_dir = Path("elevator_saga/traffic")
        if traffic_dir.exists():
            traffic_files = sorted([f for f in traffic_dir.glob("*.json") if f.is_file()])
            scenario_index = self.scenario_count - 1
            if scenario_index < len(traffic_files):
                self.current_scenario_name = traffic_files[scenario_index].stem
            else:
                self.current_scenario_name = f"scenario_{scenario_index + 1}"
        else:
            self.current_scenario_name = f"scenario_{self.scenario_count}"
        
        print(f"\n{'='*60}")
        print(f"[场景] 开始记录场景 {self.scenario_count}: {self.current_scenario_name}")
        print(f"{'='*60}\n")
        
        # 记录初始状态
        state = self.api_client.get_state()
        self.current_scenario_frames.append(self._serialize_state(state, []))
        
    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], 
        elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """每个tick开始时记录状态"""
        super().on_event_execute_start(tick, events, elevators, floors)
        
        # 记录当前帧
        state = self.api_client.get_state()
        self.current_scenario_frames.append(self._serialize_state(state, events))
        
        # 显示进度
        if tick % 50 == 0 and tick > 0:
            progress = tick * 100 // self.current_traffic_max_tick
            print(f"   记录中... {tick}/{self.current_traffic_max_tick} ticks ({progress}%)")
    
    def _run_event_driven_simulation(self) -> None:
        """运行模拟（覆盖父类方法以处理场景切换）"""
        # 运行当前场景
        super()._run_event_driven_simulation()
        
        # 场景完成后保存数据
        self._save_current_scenario()
        
        # 检查是否还有更多场景
        if self.scenario_count < self.max_scenarios:
            print(f"\n[切换] 切换到下一个场景...")
            if self.api_client.next_traffic_round(full_reset=False):
                time.sleep(0.5)
                # 递归运行下一个场景
                self._run_event_driven_simulation()
            else:
                print("[完成] 所有场景已录制完成")
                self._save_all_data()
        else:
            print(f"\n[完成] 已录制 {self.max_scenarios} 个场景")
            self._save_all_data()
    
    def _save_current_scenario(self):
        """保存当前场景"""
        if not self.current_scenario_frames:
            return
        
        state = self.api_client.get_state()
        
        scenario_data = {
            "scenario_name": self.current_scenario_name,
            "max_tick": self.current_traffic_max_tick,
            "total_frames": len(self.current_scenario_frames),
            "frames": self.current_scenario_frames,
            "final_metrics": self._serialize_metrics(state.metrics),
            "building_info": {
                "floors": len(state.floors),
                "elevators": len(state.elevators),
                "max_capacity": state.elevators[0].max_capacity if state.elevators else 0
            }
        }
        
        self.scenarios_data.append(scenario_data)
        
        metrics = state.metrics
        print(f"\n[OK] 场景 {self.scenario_count} 记录完成！")
        print(f"   - 场景名称: {self.current_scenario_name}")
        print(f"   - 记录了 {len(self.current_scenario_frames)} 帧")
        print(f"   - 完成乘客: {metrics.completed_passengers}/{metrics.total_passengers}")
        print(f"   - 完成率: {metrics.completion_rate*100:.1f}%")
    
    def _save_all_data(self):
        """保存所有数据到文件"""
        print(f"\n{'='*60}")
        print("[保存] 正在保存数据到 simulation_data.json...")
        print(f"{'='*60}\n")
        
        output_data = {
            "version": "1.0",
            "total_scenarios": len(self.scenarios_data),
            "metadata": {
                "algorithm": "OptimizedLOOK",
                "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_frames": sum(s["total_frames"] for s in self.scenarios_data)
            },
            "scenarios": self.scenarios_data
        }
        
        with open("simulation_data.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        import os
        file_size = os.path.getsize("simulation_data.json") / (1024 * 1024)
        
        print("[OK] 数据已保存！")
        print(f"   - 文件: simulation_data.json")
        print(f"   - 大小: {file_size:.2f} MB")
        print(f"   - 场景数: {len(self.scenarios_data)}")
        print(f"   - 总帧数: {sum(s['total_frames'] for s in self.scenarios_data)}")
        print(f"\n{'='*60}")
        print("[完成] 记录完成！现在可以打开 index.html 查看可视化")
        print(f"{'='*60}\n")
    
    def _serialize_state(self, state: Any, events: List[Any]) -> Dict[str, Any]:
        """序列化状态"""
        # 只记录活跃乘客（waiting或in_elevator），不记录已完成的
        active_passengers = {
            str(pid): self._serialize_passenger(p) 
            for pid, p in state.passengers.items()
            if hasattr(p.status, 'value') and p.status.value != 'completed'
        }
        
        return {
            "tick": state.tick,
            "elevators": [self._serialize_elevator(e) for e in state.elevators],
            "floors": [self._serialize_floor(f) for f in state.floors],
            "passengers": active_passengers,
            "metrics": self._serialize_metrics(state.metrics),
            "events": [self._serialize_event(e) for e in events]
        }
    
    def _serialize_elevator(self, elevator: Any) -> Dict[str, Any]:
        """序列化电梯"""
        return {
            "id": elevator.id,
            "current_floor": elevator.current_floor,
            "current_floor_float": elevator.current_floor_float,
            "target_floor": elevator.target_floor if elevator.target_floor is not None else elevator.current_floor,
            "passengers": list(elevator.passengers),
            "passenger_count": len(elevator.passengers),
            "max_capacity": elevator.max_capacity,
            "load_factor": len(elevator.passengers) / elevator.max_capacity if elevator.max_capacity > 0 else 0,
            "run_status": elevator.run_status.value if hasattr(elevator.run_status, 'value') else str(elevator.run_status),
            "direction": elevator.target_floor_direction.value if hasattr(elevator.target_floor_direction, 'value') else str(elevator.target_floor_direction),
            "last_direction": elevator.last_tick_direction.value if hasattr(elevator.last_tick_direction, 'value') else str(elevator.last_tick_direction),
            "is_idle": elevator.is_idle,
            "is_full": len(elevator.passengers) >= elevator.max_capacity,
            "pressed_floors": elevator.pressed_floors,
            "floor_up_position": elevator.position.floor_up_position
        }
    
    def _serialize_floor(self, floor: Any) -> Dict[str, Any]:
        """序列化楼层"""
        return {
            "floor": floor.floor,
            "up_queue": list(floor.up_queue),
            "down_queue": list(floor.down_queue),
            "up_queue_count": len(floor.up_queue),
            "down_queue_count": len(floor.down_queue),
            "total_waiting": len(floor.up_queue) + len(floor.down_queue)
        }
    
    def _serialize_passenger(self, passenger: Any) -> Dict[str, Any]:
        """序列化乘客"""
        return {
            "id": passenger.id,
            "origin": passenger.origin,
            "destination": passenger.destination,
            "arrive_tick": passenger.arrive_tick,
            "status": passenger.status.value if hasattr(passenger.status, 'value') else str(passenger.status)
        }
    
    def _serialize_metrics(self, metrics: Any) -> Dict[str, Any]:
        """序列化性能指标"""
        return {
            "completed_passengers": metrics.completed_passengers,
            "total_passengers": metrics.total_passengers,
            "completion_rate": metrics.completion_rate,
            "average_floor_wait_time": metrics.average_floor_wait_time,
            "p95_floor_wait_time": metrics.p95_floor_wait_time,
            "average_arrival_wait_time": metrics.average_arrival_wait_time,
            "p95_arrival_wait_time": metrics.p95_arrival_wait_time
        }
    
    def _serialize_event(self, event: Any) -> Dict[str, Any]:
        """序列化事件"""
        if hasattr(event, 'type'):
            return {
                "tick": event.tick if hasattr(event, 'tick') else 0,
                "type": event.type.value if hasattr(event.type, 'value') else str(event.type),
                "data": event.data if hasattr(event, 'data') else {}
            }
        else:
            return event


if __name__ == "__main__":
    print("[启动] 启动带算法的数据记录器\n")
    print("提示：")
    print("1. 确保服务器已启动（python -m elevator_saga.server.simulator）")
    print("2. 本程序会自动启动算法客户端")
    print("3. 预计耗时 2-5 分钟\n")
    
    input("按 Enter 开始录制...")
    
    controller = RecordingController()
    controller.start()
