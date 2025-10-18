#!/usr/bin/env python3
"""
电梯可视化系统启动脚本
一键启动服务器、算法和数据记录
"""
import sys
import time
import subprocess
import webbrowser
from pathlib import Path


def print_banner():
    """打印标题"""
    print("\n" + "="*70)
    print("电梯调度可视化系统 - 一键启动")
    print("="*70 + "\n")


def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 10):
        print("[错误] 需要 Python 3.10 或更高版本")
        print(f"   当前版本: {sys.version}")
        sys.exit(1)
    print("[OK] Python 版本检查通过")


def check_dependencies():
    """检查依赖"""
    print("\n[检查] 依赖...")
    required = ['flask', 'numpy']
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"   [OK] {package}")
        except ImportError:
            print(f"   [X] {package} (未安装)")
            missing.append(package)
    
    if missing:
        print(f"\n[警告] 缺少依赖: {', '.join(missing)}")
        print("   请运行: pip install flask numpy")
        sys.exit(1)


def check_files():
    """检查必要文件"""
    print("\n[检查] 文件...")
    
    required_files = [
        'elevator_saga/server/simulator.py',
        'elevator_saga/client_examples/our_example.py',
        'record.py',
        'index.html'
    ]
    
    for file in required_files:
        if Path(file).exists():
            print(f"   [OK] {file}")
        else:
            print(f"   [X] {file} (不存在)")
            sys.exit(1)


def start_server():
    """启动服务器"""
    print("\n[启动] 服务器...")
    
    if sys.platform == "win32":
        # Windows
        server_process = subprocess.Popen(
            [sys.executable, "-m", "elevator_saga.server.simulator"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Linux/Mac
        server_process = subprocess.Popen(
            [sys.executable, "-m", "elevator_saga.server.simulator"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    print("   [OK] 服务器已启动（新窗口）")
    print("   [等待] 服务器就绪...")
    time.sleep(3)
    
    return server_process


def record_data():
    """记录数据"""
    print("\n[录制] 开始记录数据（运行优化算法）...")
    print("   [警告] 请等待记录完成，不要中断！")
    print("   [信息] 预计耗时 2-5 分钟\n")
    
    input("   按 Enter 开始录制...")
    
    try:
        # 运行带算法的录制器
        subprocess.run(
            [sys.executable, "record.py"],
            check=True
        )
        
        print("\n[OK] 数据记录完成！")
        return True
        
    except KeyboardInterrupt:
        print("\n[警告] 用户中断了记录")
        return False
    except subprocess.CalledProcessError as e:
        print(f"\n[错误] 记录失败: 退出代码 {e.returncode}")
        return False
    except Exception as e:
        print(f"\n[错误] 记录失败: {e}")
        return False


def start_web_server():
    """启动Web服务器"""
    print("\n[Web] 启动 Web 服务器...")
    
    if sys.platform == "win32":
        # Windows
        web_process = subprocess.Popen(
            [sys.executable, "-m", "http.server", "8080"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Linux/Mac
        web_process = subprocess.Popen(
            [sys.executable, "-m", "http.server", "8080"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    print("   [OK] Web 服务器已启动在 http://localhost:8080")
    time.sleep(2)
    
    return web_process


def open_browser():
    """打开浏览器"""
    print("\n[浏览器] 打开浏览器...")
    
    url = "http://localhost:8080/index.html"
    try:
        webbrowser.open(url)
        print(f"   [OK] 已打开 {url}")
    except Exception as e:
        print(f"   [警告] 自动打开失败: {e}")
        print(f"   请手动打开: {url}")


def cleanup(processes):
    """清理进程"""
    print("\n[清理] 正在清理...")
    
    for process in processes:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    
    print("   [OK] 清理完成")


def main():
    """主函数"""
    print_banner()
    
    processes = []
    
    try:
        # 检查环境
        check_python_version()
        check_dependencies()
        check_files()
        
        # 询问模式
        print("\n" + "="*70)
        print("请选择模式：")
        print("  1. 完整流程（推荐）- 启动服务器、运行优化算法并记录数据、打开可视化")
        print("  2. 仅数据记录 - 假设服务器已在运行")
        print("  3. 仅可视化 - 假设 simulation_data.json 已存在")
        print("="*70)
        
        choice = input("\n请输入选择 (1/2/3): ").strip()
        
        if choice == "1":
            # 完整流程
            print("\n[启动] 开始完整流程...")
            
            # 1. 启动服务器
            server_process = start_server()
            processes.append(server_process)
            
            # 2. 运行优化算法并记录数据
            #    （record.py 包含算法逻辑）
            success = record_data()
            
            if not success:
                cleanup(processes)
                sys.exit(1)
            
            # 3. 停止服务器
            print("\n[停止] 停止服务器...")
            cleanup(processes)
            processes.clear()
            
            # 4. 启动Web服务器
            web_process = start_web_server()
            processes.append(web_process)
            
            # 5. 打开浏览器
            open_browser()
            
            print("\n" + "="*70)
            print("[OK] 系统已启动！")
            print("="*70)
            print("\n[提示]")
            print("   - Web 服务器正在运行")
            print("   - 可视化界面已在浏览器中打开")
            print("   - 按 Ctrl+C 退出\n")
            
            # 等待用户中断
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n[退出] 用户退出")
        
        elif choice == "2":
            # 仅记录数据
            print("\n[录制] 仅数据记录模式...")
            print("[警告] 请确保服务器已在运行！")
            print("   （算法已集成在录制器中）\n")
            
            success = record_data()
            
            if success:
                print("\n[OK] 数据已记录！")
                print("   现在可以运行模式3查看可视化")
        
        elif choice == "3":
            # 仅可视化
            print("\n[Web] 仅可视化模式...")
            
            # 检查数据文件
            if not Path("simulation_data.json").exists():
                print("[错误] 未找到 simulation_data.json")
                print("   请先运行模式1或2生成数据")
                sys.exit(1)
            
            print("[OK] 找到数据文件")
            
            # 启动Web服务器
            web_process = start_web_server()
            processes.append(web_process)
            
            # 打开浏览器
            open_browser()
            
            print("\n" + "="*70)
            print("[OK] 可视化界面已启动！")
            print("="*70)
            print("\n[提示]")
            print("   - Web 服务器正在运行")
            print("   - 按 Ctrl+C 退出\n")
            
            # 等待用户中断
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n[退出] 用户退出")
        
        else:
            print("[错误] 无效的选择")
            sys.exit(1)
    
    except Exception as e:
        print(f"\n[错误] 发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cleanup(processes)
        print("\n[再见] 再见！\n")


if __name__ == "__main__":
    main()

