"""
scheduler.py

Preserves the original Operating Systems scheduling features:

    - FCFS scheduling
    - SJF scheduling
    - Priority scheduling
    - Average waiting / turnaround time
    - Automatic scheduler recommendation
    - Safe process-priority optimization (lowering scheduling priority)
"""

import platform

import psutil


def calculate_burst(process):
    """Estimate CPU burst size of a process from its CPU percentage."""
    return max(1, round(process["cpu"]))


# ======================================================================
# SCHEDULING ALGORITHMS
# ======================================================================


def fcfs_scheduler(processes):
    """First Come First Served scheduling for the top processes."""
    selected = processes[:5]
    if not selected:
        return []

    result = []
    current_time = 0

    for process in selected:
        burst = calculate_burst(process)
        waiting = current_time
        current_time += burst
        turnaround = current_time
        result.append(
            {
                "pid": process["pid"],
                "name": process["name"],
                "burst": burst,
                "waiting": waiting,
                "turnaround": turnaround,
            }
        )
    return result


def sjf_scheduler(processes):
    """Shortest Job First scheduling for the top processes."""
    selected = processes[:5]
    if not selected:
        return []

    selected = sorted(selected, key=calculate_burst)

    result = []
    current_time = 0

    for process in selected:
        burst = calculate_burst(process)
        waiting = current_time
        current_time += burst
        turnaround = current_time
        result.append(
            {
                "pid": process["pid"],
                "name": process["name"],
                "burst": burst,
                "waiting": waiting,
                "turnaround": turnaround,
            }
        )
    return result


def priority_scheduler(processes):
    """Priority scheduling based on CPU (70%) and memory (30%) load."""
    selected = processes[:5]
    if not selected:
        return []

    for process in selected:
        process["priority"] = (
            process["cpu"] * 0.7 + process["memory"] * 0.3
        )

    selected.sort(key=lambda p: p["priority"], reverse=True)

    result = []
    current_time = 0

    for process in selected:
        burst = calculate_burst(process)
        waiting = current_time
        current_time += burst
        turnaround = current_time
        result.append(
            {
                "pid": process["pid"],
                "name": process["name"],
                "priority": process["priority"],
                "burst": burst,
                "waiting": waiting,
                "turnaround": turnaround,
            }
        )
    return result


# ======================================================================
# AVERAGE CALCULATIONS
# ======================================================================


def calculate_average(result):
    """Return (average waiting, average turnaround) for a schedule."""
    if not result:
        return 0.0, 0.0

    average_waiting = sum(x["waiting"] for x in result) / len(result)
    average_turnaround = sum(x["turnaround"] for x in result) / len(result)

    return average_waiting, average_turnaround


# ======================================================================
# SMART SCHEDULER RECOMMENDATION
# ======================================================================


def recommend_scheduler(processes):
    """Pick the scheduler with the lowest predicted waiting time."""
    if not processes:
        return "FCFS"

    fcfs = fcfs_scheduler(processes)
    sjf = sjf_scheduler(processes)
    priority = priority_scheduler(processes)

    fcfs_wait, _ = calculate_average(fcfs)
    sjf_wait, _ = calculate_average(sjf)
    priority_wait, _ = calculate_average(priority)

    scores = {
        "FCFS": fcfs_wait,
        "SJF": sjf_wait,
        "PRIORITY": priority_wait,
    }
    return min(scores, key=scores.get)


def scheduler_reason(recommendation):
    """Human-readable justification for a scheduler recommendation."""
    if recommendation == "SJF":
        return "Best predicted waiting time for the current workload."
    if recommendation == "PRIORITY":
        return "High-resource processes require priority-based handling."
    return "Current workload is suitable for sequential scheduling."


def scheduler_analysis_text(processes):
    """Full textual analysis: recommendation + averages for each algorithm with human-friendly explanations."""
    if not processes:
        return "No active applications found to analyze."

    recommendation = recommend_scheduler(processes)
    fcfs = fcfs_scheduler(processes)
    sjf = sjf_scheduler(processes)
    priority = priority_scheduler(processes)

    fcfs_wait, fcfs_turn = calculate_average(fcfs)
    sjf_wait, sjf_turn = calculate_average(sjf)
    priority_wait, priority_turn = calculate_average(priority)

    explanations = {
        "SJF": "Shortest Job First (SJF) completes small tasks first, minimizing the average delay for all applications.",
        "PRIORITY": "Priority Scheduling handles high-resource applications first to keep the system responsive.",
        "FCFS": "First-Come First-Served (FCFS) processes tasks strictly in arrival order.",
    }

    return (
        "Operating System Task Scheduling Analysis\n"
        "═══════════════════════════════════════════\n\n"
        f"⭐ Recommended Strategy: {recommendation}\n"
        f"{explanations.get(recommendation, '')}\n\n"
        "Predicted Wait Time (lower is better):\n"
        f"  • FCFS (Sequential)     : {fcfs_wait:.2f} units\n"
        f"  • SJF (Shortest first)   : {sjf_wait:.2f} units\n"
        f"  • Priority (Load-based)  : {priority_wait:.2f} units\n\n"
        "Predicted Completion Time (lower is better):\n"
        f"  • FCFS (Sequential)     : {fcfs_turn:.2f} units\n"
        f"  • SJF (Shortest first)   : {sjf_turn:.2f} units\n"
        f"  • Priority (Load-based)  : {priority_turn:.2f} units\n\n"
        "Conclusion:\n"
        f"{scheduler_reason(recommendation)}"
    )


# ======================================================================
# PROCESS OPTIMIZATION (priority lowering, never termination)
# ======================================================================


def optimize_process(pid):
    """Lower the CPU scheduling priority of a process.

    The process is never terminated. On Windows the priority class is
    lowered; on macOS/Linux the nice value is increased.
    """
    try:
        process = psutil.Process(pid)
        name = process.name()

        system = platform.system()

        if system == "Windows":
            process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            current_nice = process.nice()
            process.nice(min(current_nice + 3, 19))

        return (True, f"Successfully lowered the workload priority of {name} (PID {pid}).\nIt will now use fewer processor cycles without interrupting your work.")

    except psutil.AccessDenied:
        return (
            False,
            "Access restricted. This system process is protected by your operating system and cannot be modified.",
        )
    except psutil.NoSuchProcess:
        return (False, "This application has already closed.")
    except psutil.ZombieProcess:
        return (False, "This application has already completed.")
    except Exception:
        return (False, "Could not adjust this application's priority because it is protected by the system.")
