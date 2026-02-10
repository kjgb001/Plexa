#!/usr/bin/env python3
"""
lesson_author.py

Plexa Lesson Author GUI (Tkinter)

- Cross-platform, zero external GUI dependencies
- Thin authoring surface: collects inputs + light validation
- Delegates all correctness/schema enforcement to lesson_generator.LessonSpec
- Supports Preview JSON + Save Lesson File + Reset
- Advanced options are collapsed by default

Place this file alongside lesson_generator.py.
Run:
  python lesson_author.py
"""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Import the generator (authoritative compiler)
try:
    from lesson_generator import LessonSpec
except Exception as e:
    raise ImportError(
        "Could not import LessonSpec from lesson_generator.py. "
        "Make sure lesson_author_ui.py and lesson_generator.py are in the same directory."
    ) from e


# UI Helpers

class ScrollableFrame(ttk.Frame):
    """A simple scrollable container using a Canvas + vertical Scrollbar."""
    def __init__(self, parent: tk.Widget, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)

        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Resize scroll region when inner frame changes
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel support (cross-platform-ish)
        self._bind_mousewheel(self.canvas)

    def _on_inner_configure(self, _evt=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, evt):
        # Make inner frame width match canvas width
        self.canvas.itemconfigure(self.inner_id, width=evt.width)

    def _bind_mousewheel(self, widget: tk.Widget):
        # Windows/macOS use <MouseWheel>; many Linux use Button-4/5
        widget.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind_all("<Button-4>", self._on_mousewheel_linux, add="+")
        widget.bind_all("<Button-5>", self._on_mousewheel_linux, add="+")

    def _on_mousewheel(self, event):
        # event.delta is 120/-120 on Windows; different on macOS
        delta = int(-1 * (event.delta / 120))
        self.canvas.yview_scroll(delta, "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")


def labeled_entry(parent: ttk.Frame, label: str, textvar: tk.StringVar, *, width: int = 40) -> ttk.Entry:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=2)
    ttk.Label(row, text=label, width=18).pack(side="left")
    ent = ttk.Entry(row, textvariable=textvar, width=width)
    ent.pack(side="left", fill="x", expand=True)
    return ent


def labeled_spinbox(parent: ttk.Frame, label: str, intvar: tk.IntVar, *, from_: int, to: int, width: int = 10) -> ttk.Spinbox:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=2)
    ttk.Label(row, text=label, width=18).pack(side="left")
    sp = ttk.Spinbox(row, from_=from_, to=to, textvariable=intvar, width=width)
    sp.pack(side="left")
    return sp


def labeled_scale(parent: ttk.Frame, label: str, doublevar: tk.DoubleVar, *, from_: float, to: float, resolution: float = 0.01) -> tk.Scale:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=4)
    ttk.Label(row, text=label, width=18).pack(side="left")
    scale = tk.Scale(
        row,
        variable=doublevar,
        from_=from_,
        to=to,
        resolution=resolution,
        orient="horizontal",
        showvalue=True,
        length=240,
    )
    scale.pack(side="left", fill="x", expand=True)
    return scale


def labeled_text(parent: ttk.Frame, label: str, *, height: int = 5) -> tk.Text:
    ttk.Label(parent, text=label).pack(anchor="w")
    container = ttk.Frame(parent)
    container.pack(fill="x", pady=(2, 8))
    txt = tk.Text(container, height=height, wrap="word")
    vsb = ttk.Scrollbar(container, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=vsb.set)
    txt.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    return txt


def get_text_value(text_widget: tk.Text) -> str:
    return text_widget.get("1.0", "end").strip()


def set_text_value(text_widget: tk.Text, value: str) -> None:
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", value or "")


# Main App

@dataclass
class PreviewState:
    lesson_spec: Optional[LessonSpec] = None
    json_str: Optional[str] = None


class LessonAuthorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Plexa Lesson Author")
        self.root.minsize(760, 720)

        # Use ttk theme where possible
        try:
            style = ttk.Style()
            # pick something reasonable; fallback if unavailable
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        self.preview_state = PreviewState()

        # Top-level layout: scrollable content + fixed footer
        self.content = ScrollableFrame(root)
        self.content.pack(fill="both", expand=True)

        self.footer = ttk.Frame(root)
        self.footer.pack(fill="x", padx=10, pady=10)

        # Build UI sections inside self.content.inner
        self._build_header(self.content.inner)
        self._build_identity(self.content.inner)
        self._build_intent(self.content.inner)
        self._build_advanced(self.content.inner)
        self._build_reflection(self.content.inner)
        self._build_footer_actions(self.footer)

        # Defaults
        self._apply_defaults()

    # Sections

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x", padx=10, pady=(10, 8))

        title = ttk.Label(header, text="Plexa Lesson Author", font=("TkDefaultFont", 16, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(header, text="Lesson Generator v0.1", foreground="#555555")
        subtitle.pack(anchor="w")

        ttk.Separator(parent).pack(fill="x", padx=10, pady=(0, 10))

    def _build_identity(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="Identity")
        card.pack(fill="x", padx=10, pady=6)

        self.title_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.course_var = tk.StringVar()
        self.unit_var = tk.StringVar()
        self.version_var = tk.StringVar()
        self.license_var = tk.StringVar()
        self.tags_var = tk.StringVar()

        labeled_entry(card, "Lesson Title*", self.title_var)
        labeled_entry(card, "Author*", self.author_var)
        labeled_entry(card, "Course", self.course_var)
        labeled_entry(card, "Unit", self.unit_var)
        labeled_entry(card, "Version*", self.version_var, width=20)

        # License combobox
        row = ttk.Frame(card)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="License*", width=18).pack(side="left")
        self.license_cb = ttk.Combobox(
            row,
            textvariable=self.license_var,
            values=["MIT", "Apache-2.0", "CC-BY", "CC-BY-SA", "Proprietary", "Custom"],
            state="readonly",
            width=18,
        )
        self.license_cb.pack(side="left")

        labeled_entry(card, "Tags", self.tags_var)  # comma-separated allowed by generator

    def _build_intent(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="Pedagogical Intent")
        card.pack(fill="x", padx=10, pady=6)

        self.learning_objective_txt = labeled_text(card, "Learning Objective*", height=5)

        # Behavioral focus (editable combobox)
        row = ttk.Frame(card)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Behavior Focus*", width=18).pack(side="left")
        self.behavior_var = tk.StringVar()
        self.behavior_cb = ttk.Combobox(
            row,
            textvariable=self.behavior_var,
            values=["hallucination", "calibration", "reasoning", "alignment", "instruction_following", "refusal", "summarization"],
            state="normal",
            width=28,
        )
        self.behavior_cb.pack(side="left", fill="x", expand=True)

        # Discipline checkboxes
        ttk.Label(card, text="Discipline").pack(anchor="w", pady=(8, 0))
        self.discipline_vars: Dict[str, tk.BooleanVar] = {}
        disciplines = ["philosophy", "cs", "management", "english", "history", "biology", "chemistry", "economics", "political_science", "other"]
        disc_frame = ttk.Frame(card)
        disc_frame.pack(fill="x", pady=2)
        for i, name in enumerate(disciplines):
            v = tk.BooleanVar(value=False)
            self.discipline_vars[name] = v
            cb = ttk.Checkbutton(disc_frame, text=name, variable=v)
            cb.grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 12), pady=2)

        # Difficulty radio buttons
        ttk.Label(card, text="Difficulty").pack(anchor="w", pady=(8, 0))
        self.difficulty_var = tk.StringVar(value="introductory")
        diff_frame = ttk.Frame(card)
        diff_frame.pack(fill="x", pady=2)
        for text, val in [("Introductory", "introductory"), ("Intermediate", "intermediate"), ("Advanced", "advanced")]:
            ttk.Radiobutton(diff_frame, text=text, value=val, variable=self.difficulty_var).pack(side="left", padx=(0, 12))

        # Optional intent fields (kept visible but small)
        self.prereq_var = tk.StringVar()
        self.approx_time_var = tk.StringVar()
        labeled_entry(card, "Prerequisites", self.prereq_var)
        labeled_entry(card, "Approx. Time", self.approx_time_var)

    def _build_advanced(self, parent: ttk.Frame) -> None:
        outer = ttk.LabelFrame(parent, text="Advanced Options")
        outer.pack(fill="x", padx=10, pady=6)

        self.advanced_shown = tk.BooleanVar(value=False)

        toggle_row = ttk.Frame(outer)
        toggle_row.pack(fill="x", pady=2)
        self.toggle_btn = ttk.Button(toggle_row, text="Show Advanced Options", command=self._toggle_advanced)
        self.toggle_btn.pack(side="left")

        self.advanced_frame = ttk.Frame(outer)
        # starts hidden; only packed when toggled

        # Execution Settings
        exec_card = ttk.LabelFrame(self.advanced_frame, text="Execution Settings")
        exec_card.pack(fill="x", pady=(8, 6))

        self.system_prompt_txt = labeled_text(exec_card, "System Prompt*", height=7)

        self.model_profile_var = tk.StringVar()
        row = ttk.Frame(exec_card)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Model Profile*", width=18).pack(side="left")
        self.model_profile_cb = ttk.Combobox(
            row,
            textvariable=self.model_profile_var,
            values=["kl3m_safe", "kl3m_base", "custom"],
            state="normal",
            width=28,
        )
        self.model_profile_cb.pack(side="left", fill="x", expand=True)

        # Initial assistant message (optional)
        self.initial_assistant_txt = labeled_text(exec_card, "Initial Assistant Message (optional)", height=4)

        # Parameters
        params_card = ttk.LabelFrame(self.advanced_frame, text="Parameters")
        params_card.pack(fill="x", pady=6)

        self.temperature_var = tk.DoubleVar(value=0.4)
        self.top_p_var = tk.DoubleVar(value=0.9)
        self.max_tokens_var = tk.IntVar(value=800)
        self.context_window_var = tk.IntVar(value=0)  # 0 => omit

        labeled_scale(params_card, "Temperature", self.temperature_var, from_=0.0, to=1.5, resolution=0.01)
        labeled_scale(params_card, "Top-p", self.top_p_var, from_=0.0, to=1.0, resolution=0.01)
        labeled_spinbox(params_card, "Max Tokens", self.max_tokens_var, from_=1, to=8192)
        # optional context window
        cw_row = ttk.Frame(params_card)
        cw_row.pack(fill="x", pady=2)
        ttk.Label(cw_row, text="Context Window", width=18).pack(side="left")
        self.cw_sp = ttk.Spinbox(cw_row, from_=0, to=200000, textvariable=self.context_window_var, width=12)
        self.cw_sp.pack(side="left")
        ttk.Label(cw_row, text="(0 = omit)", foreground="#555").pack(side="left", padx=(8, 0))

        # Capabilities
        caps_card = ttk.LabelFrame(self.advanced_frame, text="Capabilities")
        caps_card.pack(fill="x", pady=6)

        self.tools_enabled_var = tk.BooleanVar(value=False)
        self.browsing_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(caps_card, text="Enable Tools", variable=self.tools_enabled_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(caps_card, text="Enable Browsing", variable=self.browsing_enabled_var).pack(anchor="w", pady=2)

        # Interaction Constraints
        constr_card = ttk.LabelFrame(self.advanced_frame, text="Interaction Constraints")
        constr_card.pack(fill="x", pady=6)

        self.input_mode_var = tk.StringVar(value="guided")
        im_row = ttk.Frame(constr_card)
        im_row.pack(fill="x", pady=2)
        ttk.Label(im_row, text="Input Mode*", width=18).pack(side="left")
        for text, val in [("Free", "free"), ("Guided", "guided"), ("Fixed", "fixed")]:
            ttk.Radiobutton(im_row, text=text, value=val, variable=self.input_mode_var).pack(side="left", padx=(0, 10))

        self.turn_limit_var = tk.IntVar(value=0)  # 0 => omit
        tl_row = ttk.Frame(constr_card)
        tl_row.pack(fill="x", pady=2)
        ttk.Label(tl_row, text="Turn Limit", width=18).pack(side="left")
        ttk.Spinbox(tl_row, from_=0, to=100, textvariable=self.turn_limit_var, width=12).pack(side="left")
        ttk.Label(tl_row, text="(0 = omit)", foreground="#555").pack(side="left", padx=(8, 0))

        self.term_cond_var = tk.StringVar()
        labeled_entry(constr_card, "Termination Cond.", self.term_cond_var)

        # Logging (optional advanced-only)
        log_card = ttk.LabelFrame(self.advanced_frame, text="Logging Policy (optional)")
        log_card.pack(fill="x", pady=6)

        self.transcript_logged_var = tk.BooleanVar(value=True)
        self.metadata_logged_var = tk.BooleanVar(value=True)
        self.anonymization_var = tk.StringVar(value="basic")

        ttk.Checkbutton(log_card, text="Transcript Logged", variable=self.transcript_logged_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(log_card, text="Metadata Logged", variable=self.metadata_logged_var).pack(anchor="w", pady=2)

        arow = ttk.Frame(log_card)
        arow.pack(fill="x", pady=2)
        ttk.Label(arow, text="Anonymization", width=18).pack(side="left")
        ttk.Combobox(
            arow,
            textvariable=self.anonymization_var,
            values=["none", "basic", "strict"],
            state="readonly",
            width=12,
        ).pack(side="left")

    def _build_reflection(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="Reflection")
        card.pack(fill="x", padx=10, pady=6)

        # Reflection prompts: dynamic list (Listbox + Add/Remove + Editor)
        ttk.Label(card, text="Reflection Prompts*").pack(anchor="w")
        rp_container = ttk.Frame(card)
        rp_container.pack(fill="x", pady=(2, 8))

        self.rp_listbox = tk.Listbox(rp_container, height=6)
        self.rp_listbox.pack(side="left", fill="both", expand=True)

        rp_btns = ttk.Frame(rp_container)
        rp_btns.pack(side="right", fill="y", padx=(8, 0))
        ttk.Button(rp_btns, text="Add", command=self._add_reflection_prompt).pack(fill="x", pady=(0, 4))
        ttk.Button(rp_btns, text="Edit", command=self._edit_reflection_prompt).pack(fill="x", pady=(0, 4))
        ttk.Button(rp_btns, text="Remove", command=self._remove_reflection_prompt).pack(fill="x")

        # Reflection timing radio buttons
        ttk.Label(card, text="Reflection Timing").pack(anchor="w", pady=(8, 0))
        self.reflection_timing_var = tk.StringVar(value="post")
        rt_frame = ttk.Frame(card)
        rt_frame.pack(fill="x", pady=2)
        for text, val in [("Post", "post"), ("Mid", "mid"), ("Mixed", "mixed")]:
            ttk.Radiobutton(rt_frame, text=text, value=val, variable=self.reflection_timing_var).pack(side="left", padx=(0, 12))

    def _build_footer_actions(self, parent: ttk.Frame) -> None:
        # Buttons are created in _build_footer_actions below; this is kept for symmetry if needed.
        pass

    # Footer

    def _build_footer_actions(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent).pack(fill="x", pady=(0, 10))

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x")

        ttk.Button(btn_row, text="Preview Lesson JSON", command=self.preview_json).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Save Lesson File", command=self.save_lesson).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Reset Form", command=self.reset_form).pack(side="right")

    # Advanced toggle

    def _toggle_advanced(self) -> None:
        shown = self.advanced_shown.get()
        if not shown:
            self.advanced_frame.pack(fill="x", padx=6, pady=(8, 6))
            self.toggle_btn.configure(text="Hide Advanced Options")
            self.advanced_shown.set(True)
        else:
            self.advanced_frame.pack_forget()
            self.toggle_btn.configure(text="Show Advanced Options")
            self.advanced_shown.set(False)

    # Reflection prompt editor

    def _add_reflection_prompt(self) -> None:
        self._prompt_editor_dialog(title="Add Reflection Prompt", initial_text="", on_save=self._insert_prompt)

    def _edit_reflection_prompt(self) -> None:
        sel = self.rp_listbox.curselection()
        if not sel:
            messagebox.showinfo("Edit Prompt", "Select a prompt to edit.")
            return
        idx = sel[0]
        current = self.rp_listbox.get(idx)
        self._prompt_editor_dialog(
            title="Edit Reflection Prompt",
            initial_text=current,
            on_save=lambda text: self._update_prompt(idx, text),
        )

    def _remove_reflection_prompt(self) -> None:
        sel = self.rp_listbox.curselection()
        if not sel:
            messagebox.showinfo("Remove Prompt", "Select a prompt to remove.")
            return
        idx = sel[0]
        self.rp_listbox.delete(idx)

    def _insert_prompt(self, text: str) -> None:
        if text.strip():
            self.rp_listbox.insert("end", text.strip())

    def _update_prompt(self, idx: int, text: str) -> None:
        text = text.strip()
        if not text:
            messagebox.showwarning("Invalid", "Prompt cannot be empty.")
            return
        self.rp_listbox.delete(idx)
        self.rp_listbox.insert(idx, text)

    def _prompt_editor_dialog(self, *, title: str, initial_text: str, on_save) -> None:
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        win.grab_set()
        win.minsize(520, 260)

        ttk.Label(win, text=title, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 6))

        txt = tk.Text(win, height=8, wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        txt.insert("1.0", initial_text or "")

        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        def _save():
            val = txt.get("1.0", "end").strip()
            if not val:
                messagebox.showwarning("Invalid", "Prompt cannot be empty.", parent=win)
                return
            on_save(val)
            win.destroy()

        ttk.Button(btn_row, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(btn_row, text="Save", command=_save).pack(side="right", padx=(0, 8))

        win.wait_window(win)

    # Defaults + Reset

    def _apply_defaults(self) -> None:
        self.version_var.set("0.1.0")
        self.license_var.set("MIT")
        self.behavior_var.set("calibration")
        self.model_profile_var.set("kl3m_safe")

        # Conservative system prompt starter
        set_text_value(
            self.system_prompt_txt,
            "You are a careful tutor. If uncertain, say so. Do not invent citations. "
            "Ask clarifying questions when needed. Keep answers concise unless asked otherwise."
        )

        # A starter reflection prompt so the form can validate immediately
        self.rp_listbox.delete(0, "end")
        self.rp_listbox.insert("end", "What did the model do well, and where did it struggle?")
        self.rp_listbox.insert("end", "What would you change about your prompt to improve the outcome?")

    def reset_form(self) -> None:
        if not messagebox.askyesno("Reset Form", "Reset all fields to defaults?"):
            return

        # Identity
        self.title_var.set("")
        self.author_var.set("")
        self.course_var.set("")
        self.unit_var.set("")
        self.version_var.set("0.1.0")
        self.license_var.set("MIT")
        self.tags_var.set("")

        # Intent
        set_text_value(self.learning_objective_txt, "")
        self.behavior_var.set("calibration")
        for v in self.discipline_vars.values():
            v.set(False)
        self.difficulty_var.set("introductory")
        self.prereq_var.set("")
        self.approx_time_var.set("")

        # Advanced / Execution
        set_text_value(self.system_prompt_txt, "")
        set_text_value(self.initial_assistant_txt, "")
        self.model_profile_var.set("kl3m_safe")

        self.temperature_var.set(0.4)
        self.top_p_var.set(0.9)
        self.max_tokens_var.set(800)
        self.context_window_var.set(0)

        self.tools_enabled_var.set(False)
        self.browsing_enabled_var.set(False)

        # Constraints
        self.input_mode_var.set("guided")
        self.turn_limit_var.set(0)
        self.term_cond_var.set("")

        # Logging
        self.transcript_logged_var.set(True)
        self.metadata_logged_var.set(True)
        self.anonymization_var.set("basic")

        # Reflection
        self.rp_listbox.delete(0, "end")
        self.reflection_timing_var.set("post")

        # Apply defaults (for starter prompts, etc.)
        self._apply_defaults()

        self.preview_state = PreviewState()

    # Data assembly

    def _collect_disciplines(self) -> Optional[List[str]]:
        selected = [name for name, var in self.discipline_vars.items() if var.get()]
        return selected if selected else None

    def _collect_reflection_prompts(self) -> List[str]:
        return [self.rp_listbox.get(i).strip() for i in range(self.rp_listbox.size()) if self.rp_listbox.get(i).strip()]

    def _light_validate(self) -> Optional[str]:
        # Very light validation; generator enforces the real rules.
        if not self.title_var.get().strip():
            return "Lesson Title is required."
        if not self.author_var.get().strip():
            return "Author is required."
        if not self.version_var.get().strip():
            return "Version is required."
        if not self.license_var.get().strip():
            return "License is required."
        if not get_text_value(self.learning_objective_txt):
            return "Learning Objective is required."
        if not self.behavior_var.get().strip():
            return "Behavioral Focus is required."
        if self.advanced_shown.get():
            if not get_text_value(self.system_prompt_txt):
                return "System Prompt is required (in Advanced Options)."
            if not self.model_profile_var.get().strip():
                return "Model Profile is required (in Advanced Options)."
        # reflection prompts required by generator
        if not self._collect_reflection_prompts():
            return "At least one Reflection Prompt is required."
        return None

    def build_raw_dict(self) -> Dict[str, Any]:
        """
        Build the flat input dict expected by LessonSpec(raw=...).
        Only include optional fields when non-empty, so generator defaults apply cleanly.
        """
        raw: Dict[str, Any] = {}

        # Identity
        raw["title"] = self.title_var.get().strip()
        raw["author"] = self.author_var.get().strip()
        raw["course"] = self.course_var.get().strip() or None
        raw["unit"] = self.unit_var.get().strip() or None
        raw["version"] = self.version_var.get().strip()
        raw["license"] = self.license_var.get().strip()
        raw["tags"] = self.tags_var.get().strip() or None  # generator accepts comma string

        # Intent
        raw["learning_objective"] = get_text_value(self.learning_objective_txt)
        raw["behavioral_focus"] = self.behavior_var.get().strip()
        raw["discipline"] = self._collect_disciplines()
        raw["difficulty"] = self.difficulty_var.get().strip() or None
        raw["prerequisites"] = self.prereq_var.get().strip() or None
        raw["approximate_time"] = self.approx_time_var.get().strip() or None

        # Execution

        # System prompt + model profile are required by generator, but we keep them visible only in Advanced.
        # If Advanced is hidden, we still provide reasonable defaults so professor doesn't have to touch it.
        system_prompt = get_text_value(self.system_prompt_txt).strip()
        if not system_prompt:
            system_prompt = (
                "You are a careful tutor. If uncertain, say so. "
                "Do not invent citations. Ask clarifying questions when needed."
            )

        model_profile = self.model_profile_var.get().strip() or "kl3m_safe"

        raw["system_prompt"] = system_prompt
        raw["model_profile"] = model_profile

        initial_msg = get_text_value(self.initial_assistant_txt)
        raw["initial_assistant_message"] = initial_msg or None

        params: Dict[str, Any] = {
            "temperature": float(self.temperature_var.get()),
            "top_p": float(self.top_p_var.get()),
            "max_tokens": int(self.max_tokens_var.get()),
        }
        cw = int(self.context_window_var.get())
        if cw > 0:
            params["context_window"] = cw
        raw["parameters"] = params

        raw["capabilities"] = {
            "tools_enabled": bool(self.tools_enabled_var.get()),
            "browsing_enabled": bool(self.browsing_enabled_var.get()),
        }

        # Constraints
        raw["input_mode"] = self.input_mode_var.get().strip() or "guided"
        tl = int(self.turn_limit_var.get())
        raw["turn_limit"] = tl if tl > 0 else None
        raw["termination_condition"] = self.term_cond_var.get().strip() or None

        # Reflection
        raw["reflection_prompts"] = self._collect_reflection_prompts()
        raw["reflection_timing"] = self.reflection_timing_var.get().strip() or "post"

        # Logging policy (optional advanced-only; safe defaults exist in generator)
        raw["logging_policy"] = {
            "transcript_logged": bool(self.transcript_logged_var.get()),
            "metadata_logged": bool(self.metadata_logged_var.get()),
            "anonymization_level": self.anonymization_var.get().strip() or "basic",
        }

        # attached_metadata optional; leave empty so generator inserts lesson_id/version
        raw["attached_metadata"] = {}

        # Drop None values to keep raw clean (generator also drops None per-category)
        raw = {k: v for k, v in raw.items() if v is not None}
        return raw

    # Generator integration

    def _build_lesson_spec(self) -> LessonSpec:
        err = self._light_validate()
        if err:
            raise ValueError(err)

        raw = self.build_raw_dict()
        return LessonSpec(raw=raw)  # generator enforces everything else

    def preview_json(self) -> None:
        try:
            spec = self._build_lesson_spec()
            js = spec.to_json_str(pretty=True)
            self.preview_state = PreviewState(lesson_spec=spec, json_str=js)
            self._show_preview_modal(js)
        except Exception as e:
            self._show_error("Preview Failed", e)

    def save_lesson(self) -> None:
        try:
            spec = self._build_lesson_spec()
            js = spec.to_json_str(pretty=True)

            # ask path
            initial_name = self._suggest_filename()
            path = filedialog.asksaveasfilename(
                title="Save Lesson File",
                defaultextension=".json",
                initialfile=initial_name,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return

            out_path = Path(path)
            if out_path.exists():
                if not messagebox.askyesno("Overwrite?", f"{out_path.name} already exists.\nOverwrite?"):
                    return

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(js, encoding="utf-8")

            self.preview_state = PreviewState(lesson_spec=spec, json_str=js)
            messagebox.showinfo("Saved", f"Lesson saved to:\n{out_path}")
        except Exception as e:
            self._show_error("Save Failed", e)

    def _suggest_filename(self) -> str:
        # Conservative filename from title + version
        title = self.title_var.get().strip().lower().replace(" ", "_")
        title = "".join(ch for ch in title if ch.isalnum() or ch in ("_", "-"))
        version = self.version_var.get().strip()
        if not title:
            title = "lesson"
        if version:
            return f"{title}_{version}.json"
        return f"{title}.json"

    # Modals

    def _show_preview_modal(self, json_str: str) -> None:
        win = tk.Toplevel(self.root)
        win.title("Lesson JSON Preview")
        win.transient(self.root)
        win.grab_set()
        win.minsize(720, 520)

        ttk.Label(win, text="Lesson JSON Preview", font=("TkDefaultFont", 11, "bold")).pack(
            anchor="w", padx=10, pady=(10, 6)
        )

        container = ttk.Frame(win)
        container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        txt = tk.Text(container, wrap="none")
        vsb = ttk.Scrollbar(container, orient="vertical", command=txt.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        txt.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")

        txt.insert("1.0", json_str)
        txt.configure(state="disabled")

        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        def _copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(json_str)
            messagebox.showinfo("Copied", "JSON copied to clipboard.", parent=win)

        ttk.Button(btn_row, text="Copy to Clipboard", command=_copy).pack(side="left")
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="right")

        win.wait_window(win)

    def _show_error(self, title: str, exc: Exception) -> None:
        # Show readable message; include details in expandable text if needed.
        msg = str(exc) if str(exc) else exc.__class__.__name__

        # For debugging, you can uncomment this:
        # msg = msg + "\n\n" + traceback.format_exc()

        messagebox.showerror(title, msg)

# Run

def main() -> int:
    root = tk.Tk()
    app = LessonAuthorApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
