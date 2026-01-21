/* =========================================
   GLOBAL VARIABLES & DOM ELEMENTS
   ========================================= */
const modal = document.getElementById('taskModal');
const taskForm = document.getElementById('taskForm');
const modalTitle = document.getElementById('modalTitle');
const modalBtn = document.getElementById('modalBtn');
const actionInput = document.getElementById('actionInput');

// Input Fields
const inpTitle = document.getElementById('inpTitle');
const inpDesc = document.getElementById('inpDesc');
const inpDate = document.getElementById('inpDate');
const inpRepeat = document.getElementById('inpRepeat');
const inpReminder = document.getElementById('inpReminder');

// Calendar Constants
const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
];

/* =========================================
   MODAL LOGIC (ADD / EDIT)
   ========================================= */

function openAddModal() {
    taskForm.reset(); 
    taskForm.action = "/add_task";
    modalTitle.innerText = "NEW DIRECTIVE";
    modalBtn.innerText = "UPLOAD TASK";
    actionInput.disabled = true; 

    // Default to local time now
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    inpDate.value = now.toISOString().slice(0, 16);

    modal.style.display = "flex";
}

function openEditModal(id) {
    const task = tasksData[id]; 
    if (!task) return console.error("Task ID not found in data:", id);

    inpTitle.value = task.title;
    inpDesc.value = task.description;
    inpDate.value = task.deadline; 
    inpRepeat.value = task.repeat;
    inpReminder.value = task.reminder;

    taskForm.action = `/update_task/${id}`;
    modalTitle.innerText = "EDIT DIRECTIVE";
    modalBtn.innerText = "UPDATE SYSTEM";
    actionInput.disabled = false; 

    modal.style.display = "flex";
}

function closeModal() {
    modal.style.display = "none";
}

window.onclick = function(event) {
    if (event.target == modal) closeModal();
}

/* =========================================
   TIMER LOGIC (REMAINING / EXPIRED)
   ========================================= */
function updateTimers() {
    const timerBadges = document.querySelectorAll('.timer-badge');
    const now = new Date();

    timerBadges.forEach(badge => {
        const deadlineStr = badge.getAttribute('data-deadline');
        if (!deadlineStr) return;

        const deadline = new Date(deadlineStr);
        if (isNaN(deadline)) {
            badge.innerText = "Invalid Date";
            return;
        }

        const diff = deadline - now;
        
        // Calculate components
        const absDiff = Math.abs(diff);
        const days = Math.floor(absDiff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((absDiff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((absDiff % (1000 * 60 * 60)) / (1000 * 60));

        let text = "";
        
        if (diff > 0) {
            // Future
            badge.classList.remove('overdue');
            if (days > 0) text = `${days}d ${hours}h left`;
            else if (hours > 0) text = `${hours}h ${minutes}m left`;
            else text = `${minutes}m left`;
        } else {
            // Past (Expired/Overdue)
            badge.classList.add('overdue');
            if (days > 0) text = `Overdue ${days}d ${hours}h`;
            else if (hours > 0) text = `Overdue ${hours}h ${minutes}m`;
            else text = `Overdue ${minutes}m`;
        }

        badge.innerText = text;
    });
}

/* =========================================
   CALENDAR LOGIC
   ========================================= */

function renderCalendar() {
    const calendar = document.getElementById('calendar');
    const calTitle = document.getElementById('calTitle');
    const yearSelect = document.getElementById('yearSelect');

    if (!calendar) return;

    calendar.innerHTML = "";
    calTitle.innerText = `${monthNames[currentMonth - 1]} ${currentYear}`;

    if (yearSelect.children.length === 0) {
        for (let y = currentYear - 5; y <= currentYear + 5; y++) {
            let opt = document.createElement('option');
            opt.value = y;
            opt.innerText = y;
            if (y === currentYear) opt.selected = true;
            yearSelect.appendChild(opt);
        }
    }

    const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
    const firstDayIndex = new Date(currentYear, currentMonth - 1, 1).getDay(); 

    for (let x = 0; x < firstDayIndex; x++) {
        let empty = document.createElement('div');
        empty.className = 'cal-day empty';
        calendar.appendChild(empty);
    }

    const todayDate = new Date();
    
    for (let i = 1; i <= daysInMonth; i++) {
        let dayDiv = document.createElement('div');
        dayDiv.className = 'cal-day';
        dayDiv.innerText = i;
        
        let dateStr = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
        
        if (i === todayDate.getDate() && currentMonth === (todayDate.getMonth() + 1) && currentYear === todayDate.getFullYear()) {
            dayDiv.classList.add('today');
        }

        if (taskDates.includes(dateStr)) {
            dayDiv.classList.add('has-task');
        }

        dayDiv.onclick = () => {
            window.location.href = `/dashboard?date=${dateStr}&month=${currentMonth}&year=${currentYear}`;
        };

        dayDiv.oncontextmenu = (e) => {
            e.preventDefault();
            openAddModal();
            document.getElementById('inpDate').value = dateStr + "T12:00";
        };

        calendar.appendChild(dayDiv);
    }
}

function changeMonth(step) {
    let newMonth = currentMonth + step;
    let newYear = currentYear;

    if (newMonth > 12) { newMonth = 1; newYear++; }
    else if (newMonth < 1) { newMonth = 12; newYear--; }

    window.location.href = `/dashboard?month=${newMonth}&year=${newYear}`;
}

function jumpToYear() {
    const y = document.getElementById('yearSelect').value;
    window.location.href = `/dashboard?month=${currentMonth}&year=${y}`;
}

/* =========================================
   INITIALIZATION
   ========================================= */

document.addEventListener('DOMContentLoaded', () => {
    renderCalendar();
    
    // Run Timer update immediately and then every 60s
    updateTimers();
    setInterval(updateTimers, 60000); 

    // Reminders check every 10s
    setInterval(() => {
        const now = new Date();
        Object.values(tasksData).forEach(t => {
            if (t.status === 'pending' && t.reminder > 0) {
                const deadlineDate = new Date(t.deadline);
                const timeDiff = deadlineDate - now; 
                const reminderMs = t.reminder * 60 * 1000; 

                if (timeDiff > 0 && timeDiff <= reminderMs) {
                    console.log(`[REMINDER] Task "${t.title}" is due soon.`);
                    // Optional: alert(`Reminder: ${t.title}`);
                }
            }
        });
    }, 10000); 
});