# Plexa Lesson Author

**Plexa Lesson Author** is a cross-platform, offline tool for creating structured lesson files used by the Plexa AI education framework.

It is designed for **faculty**, not developers:
- No installation steps beyond Python
- No internet connection required
- No accounts, servers, or configuration
- Just open it, author a lesson, and save a file

The tool produces portable JSON lesson artifacts that Plexa can import and run deterministically.

---

## What This Is

- A **lesson authoring GUI** built with Python and Tkinter
- A **thin frontend** over a strict lesson schema
- A way to create lessons without touching code

## What This Is Not

- Not a chat interface
- Not an AI execution environment
- Not a data collection or analytics tool
- Not tied to any backend or cloud service

---

## Requirements

- **Python 3.9 or newer**
  - Windows: install from https://www.python.org
  - macOS: system Python is sufficient on most versions
  - Linux: available via system package manager if not included

No additional Python packages are required.

---

## How to Open the Lesson Author

Navigate to the launch folder:

### Windows
Double-click:
```
Lesson_Author_Windows.bat
```

### macOS
Double-click:
```
Lesson_Author_macOS.command
```
> On first run, macOS may require right-click → Open.

### Linux

Make exectuable with ```chmod +x ./Lesson_Author_Linux.sh```

Double-click:
```
Lesson_Author_Linux.sh
```
or run from a terminal:
```
./Lesson_Author_Linux.sh
```  

**OR**

Run the python file directly from the terminal:

```python3 ./lesson_author.py```


---

## Files in This Repository

```
Plexa-Lesson-Author/
├─ lesson_author_ui.py      # GUI application (Tkinter)
├─ lesson_generator.py      # Lesson schema + validation (authoritative)
├─ launch/                  # OS-specific launch scripts
└─ README.md
```

- `lesson_generator.py` is the **single source of truth** for lesson validity
- `lesson_author.py` only collects inputs and displays errors
- Lessons are saved as standard `.json` files

---

## Output

The Lesson Author generates **lesson JSON files** that can be:
- Imported into Plexa
- Versioned in git
- Shared with colleagues
- Archived or reused across semesters

Lessons are static, declarative, and portable.

---

## License

Copyright 2026 Kellan Guinn-Bailey

See [License](LICENSE) Apache-2.0

---

## About Plexa

Plexa is an educational framework for **experiential AI literacy**, designed to help students understand how language models behave through structured interaction rather than free-form chat.

The Lesson Author is one component of the broader Plexa ecosystem.

