#!/usr/bin/env python3
from typing import List, Dict

from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction, SimulationEvent


class TestElevatorBusController(ElevatorController):
    def __init__(self):
        super().__init__("http://127.0.0.1:8000", True)
        self.pending_calls: List[ProxyPassenger] = []      # 所有的请求
        self.max_floor = 0                                 # 最高楼层是多少，后面会维护的
        self.floors: List[ProxyFloor] = []                 # 所有楼层
        self.elevators: List[ProxyElevator] = []           # 所有电梯
        self.elevator_targets: Dict[int, List[int]] = {}   # 每个电梯都有一个目标楼层列表
        

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        self.max_floor = floors[-1].floor                                           # 维护最高楼层
        self.floors = floors                                                        # 得到所有楼层组成的列表
        self.elevators = elevators                                                  # 得到所有电梯组成的列表
        print("最高楼层：", self.max_floor)
        print("电梯数量：", len(self.elevators))
        self.elevator_targets: Dict[int, List[int]] = {e.id: [] for e in elevators} # 每个电梯的目标楼层列表初始化为空
        # 小trick：让所有电梯均匀分布在所有楼层中，现在立即移动。
        #for i, elevator in enumerate(elevators):
        #    target_floor = (i * (len(floors) - 1)) // len(elevators)
        #    elevator.go_to_floor(target_floor, immediate=True)

    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        print(f"Tick {tick}: 即将处理 {len(events)} 个事件 {[e.type.value for e in events]}")
        for i in elevators:
            print(
                f"\t{i.id}:[{i.target_floor_direction.value},{i.current_floor_float}/{i.target_floor}]"
                + "num_passengers" + f"{len(i.passengers)}", end="")
        print()

    def on_event_execute_end(
        self, tick: int, events: List[SimulationEvent], elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        pass

    def on_passenger_call(self, passenger:ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        print(f"乘客 {passenger.id} 在 F{floor.floor} 请求 {direction} -> 目标是F{passenger.destination}")
        best_elevator = None
        best_distance = 999999
        # 遍历所有电梯，直到找到最合适的
        for idx, elevator in enumerate(self.elevators):
            moving_dir = elevator.last_tick_direction
            #print("电梯序号：", idx)
            #print("moving_dir:", moving_dir)
            
            # 电梯距乘客的距离楼层数
            distance = abs(elevator.current_floor - floor.floor)
            #print("distance:", distance)
            #print("direction:", direction)
            #print("Direction.UP.value:", Direction.UP.value)
            #print(":", )
            # 规则 1: 优先同向且顺路
            '''if moving_dir == direction:
                if (direction == Direction.UP.value and elevator.current_floor <= floor.floor) or (direction == Direction.DOWN.value and elevator.current_floor >= floor.floor):
                    if distance < best_distance:
                        best_elevator = elevator
                        best_distance = distance'''

            # 规则 2: 若无顺路，则选空闲的最近者
            if moving_dir == Direction.STOPPED and distance < best_distance and best_elevator is None:
                best_elevator = elevator
                best_distance = distance

        # 规则 3: 如果都没有，暂存请求
        if best_elevator:
            print(f"分配 E{best_elevator.id} 去 F{floor.floor} 接乘客{passenger.id}")
            self.add_stop(best_elevator, floor.floor)
            if self.elevator_targets[best_elevator.id]:
                next_floor = self.elevator_targets[best_elevator.id].pop(0)
                best_elevator.go_to_floor(next_floor)
            self.add_stop(best_elevator, passenger.destination)
        else:
            print(f"乘客{passenger.id}暂无可用电梯，等待空闲后再调度")
            self.pending_calls.append(passenger)

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        pass

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        # 电梯空闲时，检查是否有等待的乘客
        print(f"E{elevator.id} 空闲了，查看是否有新任务，现在在{elevator.position.current_floor}层")
        if self.elevator_targets[elevator.id]:
            next_floor = self.elevator_targets[elevator.id].pop(0)
            elevator.go_to_floor(next_floor)
            print(f"调度 E{elevator.id} 去F{next_floor}")
        elif self.pending_calls:
            passenger = self.pending_calls.pop(0)
            print(f"调度 E{elevator.id} 去接乘客 {passenger.id} (F{passenger.origin})")
            self.add_stop(elevator, passenger.origin)
            if self.elevator_targets[elevator.id]:
                next_floor = self.elevator_targets[elevator.id].pop(0)
                elevator.go_to_floor(next_floor)
        else:
            print(f"E{elevator.id} 暂无任务")

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        print(f"乘客 {passenger.id} 上了 E{elevator.id}, 目标是 F{passenger.destination}")
        self.add_stop(elevator, passenger.destination)
        if self.elevator_targets[elevator.id]:
            next_floor = self.elevator_targets[elevator.id].pop(0)
            elevator.go_to_floor(next_floor)

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        print(f"乘客 {passenger.id} 在 F{floor.floor} 下电梯")

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        pass
    
    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        #print("乘客数:", len(elevator.passengers))
        for passenger in list(self.pending_calls):
            # 判断顺路乘客
            if passenger.origin == floor.floor:
                if direction == Direction.UP.value and passenger.destination > passenger.origin:
                    is_ordered = True
                elif direction == Direction.DOWN.value and passenger.destination < passenger.origin:
                    is_ordered = True
                else:
                    is_ordered = False

                if is_ordered:
                    print(f"E{elevator.id} 顺路接乘客 {passenger.id} 在 F{floor.floor}")
                    self.pending_calls.remove(passenger)
                    # 保存当前目标楼层（如果有且不等于当前楼层）
                    current_target = elevator.target_floor
                    if current_target is not None and current_target != floor.floor:
                        self.add_stop(elevator, current_target)
                    # 将新乘客目的地加入目标列表
                    self.add_stop(elevator, passenger.destination)
                    # 让电梯先停在顺路乘客楼层
                    elevator.go_to_floor(floor.floor)

    def add_stop(self, elevator, floor):  # 给某一个电梯的目的地列表加入新的目的地
        targets = self.elevator_targets[elevator.id]
        if floor not in targets:
            targets.append(floor)
            targets.sort(reverse=(elevator.last_tick_direction == Direction.DOWN.value))
    

if __name__ == "__main__":
    algorithm = TestElevatorBusController()
    algorithm.start()
