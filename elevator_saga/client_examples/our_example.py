#!/usr/bin/env python3
"""
优化的电梯调度算法 - 基于LOOK算法和负载均衡
目标: 最小化所有乘客的总等待时间

核心策略:
1. 同向顺路优先（LOOK算法）- 电梯在当前方向上接送所有顺路乘客
2. 负载均衡 - 考虑电梯载客量，避免过载
3. 智能电梯选择 - 综合距离、方向、负载评分
4. SCAN算法排序 - 目标楼层按方向排序，减少往返
5. 动态pending管理 - 优先处理等待时间长的请求
6. 预测性分散 - 空闲电梯移动到战略位置
"""
from typing import List, Dict, Optional
from elevator_saga.client.base_controller import ElevatorController
from elevator_saga.client.proxy_models import ProxyElevator, ProxyFloor, ProxyPassenger
from elevator_saga.core.models import Direction, SimulationEvent


class TestElevatorBusController(ElevatorController):
    def __init__(self):
        super().__init__("http://127.0.0.1:8000", True)
        self.pending_calls: List[ProxyPassenger] = []      # 等待分配的乘客
        self.max_floor = 0                                 # 最高楼层
        self.floors: List[ProxyFloor] = []                 # 所有楼层
        self.elevators: List[ProxyElevator] = []           # 所有电梯
        self.elevator_targets: Dict[int, List[int]] = {}   # 每个电梯的目标楼层列表
        self.passenger_waiting_time: Dict[int, int] = {}   # 乘客等待时间（用于优先级）
        self.current_tick = 0                              # 当前tick

    def on_init(self, elevators: List[ProxyElevator], floors: List[ProxyFloor]) -> None:
        """初始化：让电梯分散到不同楼层以提高覆盖范围"""
        self.max_floor = floors[-1].floor
        self.floors = floors
        self.elevators = elevators
        self.elevator_targets = {e.id: [] for e in elevators}
        
        print(f"[初始化] {len(floors)}层楼, {len(elevators)}部电梯, 最高楼层F{self.max_floor}")
        
        # 让电梯均匀分散到各楼层（提升初始覆盖）
        if len(elevators) > 1:
            for i, elevator in enumerate(elevators):
                target_floor = int((i * self.max_floor) / (len(elevators) - 1))
                print(f"  电梯{elevator.id} → F{target_floor}")
                elevator.go_to_floor(target_floor, immediate=True)

    def on_event_execute_start(
        self, tick: int, events: List[SimulationEvent], 
        elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """每个tick开始时更新状态"""
        self.current_tick = tick
        # 更新pending乘客的等待时间（过滤掉已经不存在的乘客）
        valid_pending = []
        for passenger in self.pending_calls:
            try:
                # 尝试访问乘客id，如果不存在会抛出异常
                pid = passenger.id
                if pid not in self.passenger_waiting_time:
                    self.passenger_waiting_time[pid] = 0
                self.passenger_waiting_time[pid] += 1
                valid_pending.append(passenger)
            except (ValueError, KeyError):
                # 乘客已经不存在了，跳过
                pass
        self.pending_calls = valid_pending

    def on_event_execute_end(
        self, tick: int, events: List[SimulationEvent], 
        elevators: List[ProxyElevator], floors: List[ProxyFloor]
    ) -> None:
        """每个tick结束时处理pending队列"""
        self._process_pending_calls()

    def on_passenger_call(self, passenger: ProxyPassenger, floor: ProxyFloor, direction: str) -> None:
        """
        乘客呼叫电梯 - 智能分配策略
        优先级：
        1. 同向顺路且未满载的电梯
        2. 空闲且最近的电梯
        3. 加入pending队列（按优先级排序）
        """
        print(f"[呼叫] 乘客{passenger.id} 在F{floor.floor}呼叫 {direction} → F{passenger.destination}")
        
        best_elevator = None
        best_score = float('inf')
        
        # 遍历所有电梯，计算分配评分
        for elevator in self.elevators:
            score = self._calculate_assignment_score(elevator, passenger, floor, direction)
            if score < best_score:
                best_score = score
                best_elevator = elevator
        
        # 如果找到合适的电梯（评分不是无穷大）
        if best_score < float('inf'):
            print(f"  [分配] 分配E{best_elevator.id} 去接乘客{passenger.id} (评分:{best_score:.1f})")
            self._assign_passenger_to_elevator(best_elevator, passenger, floor)
        else:
            print(f"  [等待] 暂无合适电梯，加入pending队列")
            if passenger not in self.pending_calls:
                self.pending_calls.append(passenger)
                self.passenger_waiting_time[passenger.id] = 0

    def _calculate_assignment_score(
        self, elevator: ProxyElevator, passenger: ProxyPassenger, 
        floor: ProxyFloor, direction: str
    ) -> float:
        """
        计算电梯分配评分（越小越好）
        考虑因素：
        1. 距离（基础分）
        2. 方向一致性（同向顺路最优）
        3. 载客量（负载均衡）
        4. 是否在路径上
        """
        # 如果电梯已满载，不能分配
        if len(elevator.passengers) >= elevator.max_capacity:
            return float('inf')
        
        distance = abs(elevator.current_floor - floor.floor)
        moving_dir = elevator.last_tick_direction
        current_floor = elevator.current_floor
        
        # 负载因子（0-1），载客越多分数越高
        load_factor = len(elevator.passengers) / elevator.max_capacity
        
        # 基础分数 = 距离 * (1 + 负载因子)
        base_score = distance * (1 + load_factor * 0.3)
        
        # 情况1: 电梯空闲 - 最优选择
        if moving_dir == Direction.STOPPED:
            return base_score * 0.7  # 给予30%的优先权
        
        # 情况2: 同向且顺路 - 非常好
        is_same_direction = (
            (moving_dir == Direction.UP and direction == Direction.UP.value) or
            (moving_dir == Direction.DOWN and direction == Direction.DOWN.value)
        )
        
        if is_same_direction:
            # 检查是否在路径上
            is_on_the_way = False
            if moving_dir == Direction.UP and current_floor <= floor.floor:
                is_on_the_way = True
            elif moving_dir == Direction.DOWN and current_floor >= floor.floor:
                is_on_the_way = True
            
            if is_on_the_way:
                # 顺路接客，优先级很高
                return base_score * 0.4  # 给予60%的优先权
            else:
                # 同向但已经过了，需要掉头
                return base_score * 2.0
        
        # 情况3: 反向运行 - 只有很近才考虑
        if distance <= 2 and len(elevator.passengers) == 0:
            return base_score * 1.5
        
        # 其他情况不分配
        return float('inf')

    def _assign_passenger_to_elevator(
        self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor
    ) -> None:
        """将乘客分配给电梯"""
        # 添加接客楼层
        self._add_stop_smart(elevator, floor.floor)
        # 添加送客楼层
        self._add_stop_smart(elevator, passenger.destination)
        
        # 如果电梯当前空闲或刚完成任务，立即发送指令
        if not self.elevator_targets[elevator.id] or elevator.target_floor == elevator.current_floor:
            self._send_next_target(elevator)

    def _add_stop_smart(self, elevator: ProxyElevator, floor: int) -> None:
        """
        智能添加目标楼层 - 使用SCAN算法排序
        根据电梯当前方向和位置，将新楼层插入到合理位置
        """
        targets = self.elevator_targets[elevator.id]
        
        if floor in targets:
            return  # 已经在目标列表中
        
        targets.append(floor)
        
        # 根据电梯当前状态排序
        current_floor = elevator.current_floor
        direction = elevator.last_tick_direction
        
        if direction == Direction.UP:
            # 上行中：先去上方楼层（从近到远），再去下方楼层（从远到近）
            targets.sort(key=lambda f: (f < current_floor, f if f >= current_floor else -f))
        elif direction == Direction.DOWN:
            # 下行中：先去下方楼层（从近到远），再去上方楼层（从远到近）
            targets.sort(key=lambda f: (f > current_floor, -f if f <= current_floor else f))
        else:
            # 停止状态：从近到远排序
            targets.sort(key=lambda f: abs(f - current_floor))

    def _send_next_target(self, elevator: ProxyElevator) -> None:
        """发送下一个目标楼层给电梯"""
        targets = self.elevator_targets[elevator.id]
        
        if targets:
            next_floor = targets[0]
            print(f"  [移动] E{elevator.id} → F{next_floor} (队列: {targets[:3]}{'...' if len(targets) > 3 else ''})")
            elevator.go_to_floor(next_floor)

    def on_elevator_idle(self, elevator: ProxyElevator) -> None:
        """
        电梯空闲时的策略：
        1. 优先处理pending队列
        2. 移动到战略位置
        """
        print(f"[空闲] E{elevator.id} 空闲在F{elevator.current_floor}")
        
        # 尝试从pending队列分配任务
        if self._try_assign_pending_to_elevator(elevator):
            return
        
        # 如果没有pending任务，移动到战略位置
        strategic_floor = self._get_strategic_position(elevator)
        if strategic_floor != elevator.current_floor:
            print(f"  [战略] 移动到战略位置F{strategic_floor}")
            elevator.go_to_floor(strategic_floor)

    def _try_assign_pending_to_elevator(self, elevator: ProxyElevator) -> bool:
        """尝试将pending乘客分配给空闲电梯"""
        if not self.pending_calls:
            return False
        
        # 找到距离最近且等待时间最长的乘客
        best_passenger = None
        best_score = float('inf')
        
        for passenger in self.pending_calls:
            try:
                distance = abs(elevator.current_floor - passenger.origin)
                waiting_time = self.passenger_waiting_time.get(passenger.id, 0)
                
                # 评分 = 距离 - 等待时间惩罚（等待越久，优先级越高）
                score = distance - waiting_time * 0.5
                
                if score < best_score:
                    best_score = score
                    best_passenger = passenger
            except (ValueError, KeyError):
                # 乘客已经不存在，跳过
                continue
        
        if best_passenger:
            try:
                print(f"  [处理] 处理pending: 乘客{best_passenger.id} 在F{best_passenger.origin} (等待{self.passenger_waiting_time[best_passenger.id]}ticks)")
                self.pending_calls.remove(best_passenger)
                floor = self.floors[best_passenger.origin]
                
                # 判断方向
                direction = Direction.UP.value if best_passenger.destination > best_passenger.origin else Direction.DOWN.value
                self._assign_passenger_to_elevator(elevator, best_passenger, floor)
                return True
            except (ValueError, KeyError):
                # 乘客在处理过程中消失了
                if best_passenger in self.pending_calls:
                    self.pending_calls.remove(best_passenger)
                return False
        
        return False

    def _get_strategic_position(self, elevator: ProxyElevator) -> int:
        """
        计算电梯的战略位置
        策略：让电梯分散到不同区域，提高响应速度
        """
        num_elevators = len(self.elevators)
        if num_elevators == 1:
            return self.max_floor // 2  # 单电梯停在中间
        
        # 多电梯时，分散到不同高度
        elevator_index = elevator.id
        return int((elevator_index * self.max_floor) / (num_elevators - 1))

    def on_elevator_stopped(self, elevator: ProxyElevator, floor: ProxyFloor) -> None:
        """电梯停靠时，移除当前楼层并发送下一个目标"""
        print(f"[停靠] E{elevator.id} 停在F{floor.floor}")
        
        targets = self.elevator_targets[elevator.id]
        if floor.floor in targets:
            targets.remove(floor.floor)
        
        # 发送下一个目标
        self._send_next_target(elevator)

    def on_passenger_board(self, elevator: ProxyElevator, passenger: ProxyPassenger) -> None:
        """乘客上梯时，确保目标楼层在列表中"""
        print(f"[上梯] 乘客{passenger.id} 上E{elevator.id} → F{passenger.destination}")
        
        # 清除该乘客的等待时间记录
        if passenger.id in self.passenger_waiting_time:
            del self.passenger_waiting_time[passenger.id]
        
        # 确保目标楼层在列表中
        self._add_stop_smart(elevator, passenger.destination)
        
        # 如果电梯当前没有目标，发送指令
        if elevator.target_floor is None or elevator.target_floor == elevator.current_floor:
            self._send_next_target(elevator)

    def on_passenger_alight(self, elevator: ProxyElevator, passenger: ProxyPassenger, floor: ProxyFloor) -> None:
        """乘客下梯"""
        print(f"[下梯] 乘客{passenger.id} 在F{floor.floor}下梯")

    def on_elevator_passing_floor(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """电梯经过楼层时触发（可用于优化）"""
        pass

    def on_elevator_approaching(self, elevator: ProxyElevator, floor: ProxyFloor, direction: str) -> None:
        """
        电梯接近楼层时，检查是否有顺路的pending乘客
        这是LOOK算法的核心：电梯在当前方向上接送所有顺路乘客
        """
        if not self.pending_calls:
            return
        
        # 检查是否可以再载客
        if len(elevator.passengers) >= elevator.max_capacity:
            return
        
        # 查找顺路的乘客
        for passenger in list(self.pending_calls):
            if passenger.origin == floor.floor:
                # 判断是否同向
                is_same_direction = False
                if direction == Direction.UP.value and passenger.destination > passenger.origin:
                    is_same_direction = True
                elif direction == Direction.DOWN.value and passenger.destination < passenger.origin:
                    is_same_direction = True
                
                if is_same_direction:
                    print(f"[顺路] E{elevator.id} 顺路接乘客{passenger.id} 在F{floor.floor} (方向:{direction})")
                    self.pending_calls.remove(passenger)
                    
                    # 确保在这层停靠
                    if floor.floor not in self.elevator_targets[elevator.id]:
                        self._add_stop_smart(elevator, floor.floor)
                    
                    # 添加乘客目的地
                    self._add_stop_smart(elevator, passenger.destination)
                    
                    # 如果当前目标不是这层，重新发送指令
                    if elevator.target_floor != floor.floor:
                        elevator.go_to_floor(floor.floor)
                    
                    # 只接一个顺路乘客，避免过度延迟
                    break

    def _process_pending_calls(self) -> None:
        """
        每个tick结束时处理pending队列
        将pending乘客分配给即将空闲的电梯
        """
        if not self.pending_calls:
            return
        
        # 找出目标列表较短的电梯（即将空闲）
        for elevator in self.elevators:
            if not self.pending_calls:
                break
            
            # 如果电梯目标列表很短（即将空闲）
            if len(self.elevator_targets[elevator.id]) <= 2:
                # 尝试分配pending乘客
                if self._try_assign_pending_to_elevator(elevator):
                    # 发送指令
                    if elevator.target_floor is None or elevator.target_floor == elevator.current_floor:
                        self._send_next_target(elevator)


if __name__ == "__main__":
    algorithm = TestElevatorBusController()
    algorithm.start()
