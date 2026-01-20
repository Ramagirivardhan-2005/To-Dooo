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

// Open Modal in "Add Mode"
function openAddModal() {
    taskForm.reset(); // Clear previous inputs
    
    // Configure for Adding
    taskForm.action = "/add_task";
    modalTitle.innerText = "NEW DIRECTIVE";
    modalBtn.innerText = "UPLOAD TASK";
    actionInput.disabled = true; // Disable the 'modify' flag

    // Set default date to Now (Local Time)
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    inpDate.value = now.toISOString().slice(0, 16);

    modal.style.display = "flex";
}

// Open Modal in "Edit Mode"
function openEditModal(id) {
    // 'tasksData' is defined in the HTML script tag
    const task = tasksData[id]; 

    if (!task) return console.error("Task data not found for ID:", id);

    // Pre-fill Form with Task Data
    inpTitle.value = task.title;
    inpDesc.value = task.description;
    inpDate.value = task.deadline; // Expects YYYY-MM-DDTHH:MM
    inpRepeat.value = task.repeat;
    inpReminder.value = task.reminder;

    // Configure for Editing
    taskForm.action = `/update_task/${id}`;
    modalTitle.innerText = "EDIT DIRECTIVE";
    modalBtn.innerText = "UPDATE SYSTEM";
    actionInput.disabled = false; // Enable 'modify' flag so backend knows it's an update

    modal.style.display = "flex";
}

// Close Modal
function closeModal() {
    modal.style.display = "none";
}

// Close if clicked outside the modal box
window.onclick = function(event) {
    if (event.target == modal) {
        closeModal();
    }
}

/* =========================================
   CALENDAR LOGIC
   ========================================= */

function renderCalendar() {
    const calendar = document.getElementById('calendar');
    const calTitle = document.getElementById('calTitle');
    const yearSelect = document.getElementById('yearSelect');

    // Safety check if we are on a page without calendar
    if (!calendar) return;

    calendar.innerHTML = ""; // Clear existing grid

    // 1. Update Header Title
    // 'currentMonth' and 'currentYear' come from HTML script tag
    calTitle.innerText = `${monthNames[currentMonth - 1]} ${currentYear}`;

    // 2. Populate Year Dropdown (Range: Current Year +/- 5)
    if (yearSelect.children.length === 0) {
        for (let y = currentYear - 5; y <= currentYear + 5; y++) {
            let opt = document.createElement('option');
            opt.value = y;
            opt.innerText = y;
            if (y === currentYear) opt.selected = true;
            yearSelect.appendChild(opt);
        }
    }

    // 3. Calculate Days
    const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
    const firstDayIndex = new Date(currentYear, currentMonth - 1, 1).getDay(); // 0 = Sunday

    // 4. Render Empty Slots (Padding for start of month)
    for (let x = 0; x < firstDayIndex; x++) {
        let empty = document.createElement('div');
        empty.className = 'cal-day empty';
        calendar.appendChild(empty);
    }

    // 5. Render Actual Days
    const todayDate = new Date();
    
    for (let i = 1; i <= daysInMonth; i++) {
        let dayDiv = document.createElement('div');
        dayDiv.className = 'cal-day';
        dayDiv.innerText = i;
        
        // Format YYYY-MM-DD for comparison
        let dateStr = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
        
        // Highlight "Today"
        if (i === todayDate.getDate() && 
            currentMonth === (todayDate.getMonth() + 1) && 
            currentYear === todayDate.getFullYear()) {
            dayDiv.classList.add('today');
        }

        // Highlight "Has Task" (Purple Underline)
        if (taskDates.includes(dateStr)) {
            dayDiv.classList.add('has-task');
        }

        // Left Click: Filter Dashboard by Date
        dayDiv.onclick = () => {
            window.location.href = `/dashboard?date=${dateStr}&month=${currentMonth}&year=${currentYear}`;
        };

        // Right Click: Quick Add Task for that Date
        dayDiv.oncontextmenu = (e) => {
            e.preventDefault();
            openAddModal();
            // Set the modal date input to clicked date at 12:00 PM
            document.getElementById('inpDate').value = dateStr + "T12:00";
        };

        calendar.appendChild(dayDiv);
    }
}

// Navigation: Prev/Next Month
function changeMonth(step) {
    let newMonth = currentMonth + step;
    let newYear = currentYear;

    // Handle Year Rollover
    if (newMonth > 12) {
        newMonth = 1;
        newYear++;
    } else if (newMonth < 1) {
        newMonth = 12;
        newYear--;
    }

    // Reload page with new context
    window.location.href = `/dashboard?month=${newMonth}&year=${newYear}`;
}

// Navigation: Jump to specific year
function jumpToYear() {
    const y = document.getElementById('yearSelect').value;
    window.location.href = `/dashboard?month=${currentMonth}&year=${y}`;
}

/* =========================================
   INITIALIZATION & NOTIFICATIONS
   ========================================= */

document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Render the Calendar
    renderCalendar();

    // 2. Start Reminder Polling Loop (Checks every 10 seconds)
    setInterval(() => {
        const now = new Date();

        // Loop through all tasks available in the global object
        Object.values(tasksData).forEach(t => {
            
            // Only check pending tasks that HAVE a reminder set
            if (t.status === 'pending' && t.reminder > 0) {
                
                const deadlineDate = new Date(t.deadline);
                const timeDiff = deadlineDate - now; // Difference in milliseconds
                const reminderMs = t.reminder * 60 * 1000; // Convert minutes to ms

                // Logic:
                // 1. Task is in the future (diff > 0)
                // 2. Task is within the reminder window (diff <= reminderMs)
                if (timeDiff > 0 && timeDiff <= reminderMs) {
                    
                    // Log to console (or use alert/Notification API)
                    console.log(`[REMINDER] Task "${t.title}" is due in ${Math.ceil(timeDiff / 60000)} minutes.`);
                    
                    // Optional: Visual visual indication or Toast could go here
                }
            }
        });

    }, 10000); // 10000 ms = 10 seconds
});