# 📋 Taskify

A modern, feature-rich web application designed to help small teams efficiently manage and track projects and tasks. With AI-powered insights and comprehensive task management capabilities, this application streamlines team collaboration and project delivery.

---

## 🎯 Features

### Core Task Management
- ✅ **Create & Manage Tasks** - Easily add new tasks with priority levels and team assignments
- 👥 **Team Assignment** - Assign tasks to specific team members for clear ownership
- 📊 **Status Tracking** - Track tasks through multiple statuses (To-Do, In Progress, Done)
- 📝 **Subtasks** - Break down complex tasks into manageable subtasks
- 🗑️ **Task Deletion** - Remove completed or unnecessary tasks

### Dashboard & Analytics
- 📈 **Interactive Dashboard** - Overview of all tasks with real-time statistics
- 🎯 **Priority-Based Organization** - High, Medium, Low priority filtering
- ⏰ **Delay Prediction** - AI-powered predictions for task delays based on priority and status
- 📅 **Task Timeline** - Track task creation dates and status updates

### AI-Powered Features
- 🤖 **AI Task Explanations** - Get detailed explanations of complex tasks using Google Gemini API
- 💡 **Smart Subtask Generation** - AI suggests relevant subtasks for complex projects
- 📊 **Intelligent Predictions** - Automatic delay risk assessment

### Data Export & Integration
- 📥 **CSV Export** - Export all tasks to CSV format for external analysis
- 💾 **Persistent Storage** - SQLite database for reliable data persistence
- 🔄 **Real-time Updates** - Instant synchronization across the application

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python 3.x, Flask |
| **Frontend** | HTML5, CSS3 |
| **Database** | SQLite3 |
| **AI Integration** | Google Generative AI (Gemini API) |
| **Environment** | Python-dotenv |
| **Utilities** | JSON, CSV |

---

## 📁 Project Structure

```
inter_team_task_manager/
├── app.py                           # Main Flask application & routes
├── test_models.py                   # Google Gemini API configuration & testing
├── .env                             # Environment variables (API keys, secrets)
├── inter_team_task.db               # SQLite database file
├── README.md                        # Project documentation
│
├── static/
│   └── css/
│       └── style.css                # Main stylesheet with animations & responsive design
│
└── templates/
    ├── layout.html                  # Base template with navbar & footer
    ├── landing.html                 # Welcome/landing page
    ├── login.html                   # User authentication page
    ├── dashboard.html               # Main dashboard with task statistics
    ├── task_list.html               # Display all tasks with filters
    ├── add_task.html                # Form to create new tasks
    ├── view_task.html               # Detailed task view with subtasks
    ├── edit_project.html            # Project editing interface
    ├── project_list.html            # List of all projects
    ├── task_explanation.html        # AI-generated task explanations
    ├── ai_suggestion.html           # AI-powered suggestions page
    ├── subtask_generator.html       # AI subtask generation interface
    └── delay_prediction.html        # Task delay risk predictions
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.7+
- pip (Python package manager)
- Google Gemini API key (optional, for AI features)

### Installation

1. **Clone or download the project:**
   ```bash
   cd inter_team_task_manager
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   source venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies:**
   ```bash
   pip install flask python-dotenv google-generativeai
   ```

4. **Set up environment variables:**
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_google_gemini_api_key_here
   FLASK_ENV=development
   ```

5. **Initialize the database:**
   The database is automatically created on first run. You can also manually initialize it by running:
   ```python
   from app import init_db
   init_db()
   ```

6. **Run the application:**
   ```bash
   python app.py
   ```

   The application will start at `http://localhost:5000`

---

## 📖 API Endpoints

### Dashboard & Views
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main dashboard with task statistics |
| GET | `/task-list` | View all tasks |
| GET | `/landing` | Landing/welcome page |

### Task Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/add-task` | Create a new task |
| GET | `/task/<task_id>` | View task details with subtasks |
| POST | `/add-subtask/<task_id>` | Add a subtask to a task |
| GET | `/update-status/<task_id>/<new_status>` | Update task status |
| GET | `/delete-task/<task_id>` | Delete a task |

### AI & Analytics Features
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/explain/<task_id>` | Get AI explanation of a task |
| GET | `/delay-prediction` | View AI predictions for task delays |
| GET | `/export-csv` | Export all tasks to CSV |

---

## 🗄️ Database Schema

### Tasks Table
```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT,                    -- Task description
    assigned_to TEXT,             -- Team member assignment
    priority TEXT,                -- High, Medium, Low
    status TEXT,                  -- To-Do, In Progress, Done
    created_at TEXT,              -- Creation timestamp
    sub_tasks TEXT,               -- JSON array of subtasks
    explanation TEXT              -- AI-generated explanation
)
```

---

## 🎨 Design Features

- **Modern UI** - Clean, intuitive interface with smooth animations
- **Responsive Design** - Works seamlessly on desktop and mobile devices
- **Color Coded Priority** - Visual indication of task priorities
- **Real-time Updates** - Instant feedback on task changes
- **Professional Styling** - Custom CSS with Poppins font and smooth transitions

---

## 🤖 AI Integration

### Google Gemini API Features

The application integrates with Google's Generative AI (Gemini) for:

1. **Task Explanations** - Provides clear, concise explanations of complex tasks
2. **Subtask Suggestions** - Recommends relevant subtasks based on task description
3. **Delay Predictions** - Analyzes task priority and status to predict delays

**Setup:**
1. Get your Gemini API key from [Google AI Studio](https://aistudio.google.com)
2. Add it to your `.env` file
3. The app gracefully falls back if API is unavailable

---

## 📊 Usage Examples

### Adding a Task
1. Navigate to "Add Task" page
2. Fill in task details (name, assignee, priority, status)
3. Click "Create Task"
4. Task appears instantly on dashboard

### Managing Subtasks
1. Click on any task to view details
2. Add subtasks to break down the work
3. Track progress through status updates
4. View all subtasks on the task detail page

---

## 🔧 Configuration

### Environment Variables
- `GEMINI_API_KEY` - Your Google Generative AI API key
- `FLASK_ENV` - Set to `development` or `production`
- `DATABASE_URL` - (Optional) Custom database path

