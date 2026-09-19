"""Custom Tk widgets for the dark chat UI: rounded buttons, segmented control, pill entry,
and a canvas-drawn message list with rounded bubbles and image previews."""

import tkinter as tk
import tkinter.font as tkfont

from client import theme as T

try:  # Pillow gives previews for JPEG/BMP/WebP; PNG/GIF work without it
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - depends on the environment
    Image = ImageTk = None


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class PillButton(tk.Canvas):
    """Rounded button / toggle chip with default, hover, pressed and disabled states."""

    def __init__(self, master, text, command, width, height, bg, fg, font, parent_bg=T.SURFACE,
                 outline=None, hover=None):
        super().__init__(master, width=width, height=height, bg=parent_bg, highlightthickness=0, bd=0)
        self.command, self.text, self.font = command, text, font
        self.w, self.h = width, height
        self._colors = dict(bg=bg, fg=fg, outline=outline, hover=hover or T.shade(bg, 1.18))
        self._enabled, self._hover, self._down = True, False, False
        self.configure(cursor="hand2")
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _set(self, **kw):
        self._hover = kw.get("hover", self._hover)
        self._down = kw.get("down", self._down)
        self._draw()

    def _release(self, _event):
        was_down = self._down
        self._set(down=False)
        if was_down and self._enabled and self.command:
            self.command()

    def restyle(self, bg=None, fg=None, outline="keep", text=None):
        if bg:
            self._colors.update(bg=bg, hover=T.shade(bg, 1.18))
        if fg:
            self._colors["fg"] = fg
        if outline != "keep":
            self._colors["outline"] = outline
        if text is not None:
            self.text = text
        self._draw()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _draw(self):
        self.delete("all")
        c = self._colors
        fill = c["bg"]
        if not self._enabled:
            fill = T.shade(c["bg"], 0.7)
        elif self._down:
            fill = T.shade(c["bg"], 0.82)
        elif self._hover:
            fill = c["hover"]
        round_rect(self, 1, 1, self.w - 1, self.h - 1, self.h / 2, fill=fill,
                   outline=c["outline"] or fill, width=1)
        color = c["fg"] if self._enabled else T.MUTED
        self.create_text(self.w / 2, self.h / 2, text=self.text, fill=color, font=self.font)


class Segmented(tk.Canvas):
    """Two-or-more option switch with an indicator that slides in ~150 ms."""

    def __init__(self, master, options, command, font, width=158, height=34, parent_bg=T.SURFACE):
        super().__init__(master, width=width, height=height, bg=parent_bg, highlightthickness=0, bd=0, cursor="hand2")
        self.options, self.command, self.font = list(options), command, font
        self.w, self.h = width, height
        self.value = self.options[0]
        self._x = 0.0
        self._anim = None
        self.bind("<Button-1>", self._click)
        self._draw()

    def _seg_w(self):
        return (self.w - 4) / len(self.options)

    def _target_x(self, value):
        return 2 + self.options.index(value) * self._seg_w()

    def _draw(self):
        self.delete("all")
        round_rect(self, 1, 1, self.w - 1, self.h - 1, self.h / 2, fill=T.INPUT, outline=T.BORDER)
        if not self._x:
            self._x = self._target_x(self.value)
        round_rect(self, self._x, 3, self._x + self._seg_w(), self.h - 3, (self.h - 6) / 2, fill=T.GREEN_DK, outline="")
        for i, name in enumerate(self.options):
            cx = 2 + i * self._seg_w() + self._seg_w() / 2
            self.create_text(cx, self.h / 2, text=name, font=self.font,
                             fill=T.TEXT if name == self.value else T.MUTED)

    def _click(self, event):
        index = min(len(self.options) - 1, max(0, int((event.x - 2) // self._seg_w())))
        self.set(self.options[index], notify=True)

    def set(self, value, notify=False, animate=True):
        if value == self.value:
            return
        self.value = value
        target, start, steps = self._target_x(value), self._x, 6
        if self._anim:
            self.after_cancel(self._anim)
        if not animate:
            self._x = target
            self._draw()
        else:
            def step(i=1):
                self._x = start + (target - start) * (i / steps)
                self._draw()
                self._anim = self.after(25, step, i + 1) if i < steps else None
            step()
        if notify and self.command:
            self.command(value)


class PillEntry(tk.Canvas):
    """Rounded text input with placeholder and focus ring. The inner Entry scrolls its
    text, so long input can never spill outside the pill."""

    def __init__(self, master, font, placeholder="", width=300, height=46, parent_bg=T.SURFACE, on_submit=None):
        super().__init__(master, width=width, height=height, bg=parent_bg, highlightthickness=0, bd=0)
        self.h, self.placeholder, self.on_submit = height, placeholder, on_submit
        self._showing_placeholder = False
        self._focus = False
        self._error = False
        self.entry = tk.Entry(self, font=font, bd=0, relief="flat", bg=T.INPUT, fg=T.TEXT,
                              insertbackground=T.TEXT, highlightthickness=0, disabledbackground=T.INPUT)
        self._window = self.create_window(0, 0, window=self.entry, anchor="w")
        self.entry.bind("<FocusIn>", lambda e: self._focus_change(True))
        self.entry.bind("<FocusOut>", lambda e: self._focus_change(False))
        self.entry.bind("<Return>", lambda e: on_submit() if on_submit else None)
        self.bind("<Configure>", lambda e: self._layout(e.width))
        self._show_placeholder()
        self._layout(width)

    def _layout(self, width):
        self.width = width
        self.coords(self._window, self.h / 2 + 4, self.h / 2)
        self.itemconfigure(self._window, width=max(10, width - self.h - 8), height=self.h - 14)
        self._draw_bg()

    def _draw_bg(self):
        self.delete("bg")
        line = T.RED if self._error else (T.BLUE if self._focus else T.BORDER)
        round_rect(self, 1, 1, self.width - 1, self.h - 1, self.h / 2, fill=T.INPUT, outline=line,
                   width=2 if (self._focus or self._error) else 1, tags="bg")
        self.tag_lower("bg")

    def _show_placeholder(self):
        self.entry.delete(0, "end")
        self.entry.insert(0, self.placeholder)
        self.entry.configure(fg=T.PLACEHOLDER)
        self._showing_placeholder = True

    def _focus_change(self, focused):
        self._focus = focused
        if focused and self._showing_placeholder:
            self.entry.delete(0, "end")
            self.entry.configure(fg=T.TEXT)
            self._showing_placeholder = False
        elif not focused and not self.entry.get():
            self._show_placeholder()
        self._draw_bg()

    def get(self) -> str:
        return "" if self._showing_placeholder else self.entry.get()

    def set(self, text: str):
        self._showing_placeholder = False
        self.entry.configure(fg=T.TEXT)
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def clear(self):
        self.entry.delete(0, "end")
        if not self._focus:
            self._show_placeholder()

    def set_error(self, error: bool):
        self._error = error
        self._draw_bg()

    def set_enabled(self, enabled: bool):
        self.entry.configure(state="normal" if enabled else "disabled")


class MessageList(tk.Canvas):
    """Scrollable chat view drawn on a canvas: rounded bubbles, image previews, and optional
    ciphertext notes under each message."""

    def __init__(self, master, body_font, small_font, mono_font):
        super().__init__(master, bg=T.SURFACE, highlightthickness=0, bd=0)
        self.body_font, self.small_font, self.mono_font = body_font, small_font, mono_font
        self.records, self.show_cipher, self._photos = [], True, []
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event):
        if self.winfo_containing(event.x_root, event.y_root) is self:
            self.yview_scroll(int(-event.delta / 120), "units")

    def add(self, side, text=None, path=None, cipher=None, kind="bubble"):
        self.records.append(dict(side=side, text=text, path=path, cipher=cipher, kind=kind,
                                 photo=self._load_photo(path) if path else None))
        self.redraw()
        self.update_idletasks()
        self.yview_moveto(1.0)

    def set_show_cipher(self, show: bool):
        self.show_cipher = show
        self.redraw()

    @staticmethod
    def _load_photo(path, box=(240, 168)):
        try:
            if Image is not None:
                img = Image.open(path)
                img.thumbnail(box)
                return ImageTk.PhotoImage(img)
            photo = tk.PhotoImage(file=path)  # PNG/GIF only without Pillow
            factor = max(1, -(-photo.width() // box[0]), -(-photo.height() // box[1]))
            return photo.subsample(factor) if factor > 1 else photo
        except Exception:
            return None

    def redraw(self):
        self.delete("all")
        width = max(self.winfo_width(), 200)
        pad, max_bubble, y = T.SP3, int(width * 0.62), T.SP2
        for rec in self.records:
            side = rec["side"]
            if rec["kind"] == "system":
                self.create_text(width / 2, y + 8, text=rec["text"], fill=T.MUTED, font=self.small_font, width=width - 2 * pad)
                y += 36
                continue
            if rec["path"]:
                y = self._draw_image(rec, side, width, pad, y)
            else:
                y = self._draw_text(rec, side, width, pad, max_bubble, y)
            if self.show_cipher and rec["cipher"]:
                label = ("sent: " if side == "out" else "received: ") + rec["cipher"]
                x = width - pad - 4 if side == "out" else pad + 4
                self.create_text(x, y - 4, text=label, fill=T.MUTED, font=self.mono_font,
                                 anchor="ne" if side == "out" else "nw")
                y += 22
            y += T.SP2
        self.configure(scrollregion=(0, 0, width, max(y, self.winfo_height())))

    def _draw_text(self, rec, side, width, pad, max_bubble, y):
        px, py = 20, 14
        item = self.create_text(0, 0, text=rec["text"], font=self.body_font, width=max_bubble - 2 * px, anchor="nw")
        x1, y1, x2, y2 = self.bbox(item)
        bw, bh = x2 - x1 + 2 * px, y2 - y1 + 2 * py
        left = width - pad - bw if side == "out" else pad
        fill, fg = (T.BLUE, "#ffffff") if side == "out" else (T.BUBBLE_IN, T.TEXT)
        self.delete(item)
        round_rect(self, left, y, left + bw, y + bh, 18, fill=fill, outline="")
        self.create_text(left + px, y + py, text=rec["text"], font=self.body_font, fill=fg, width=max_bubble - 2 * px, anchor="nw")
        return y + bh + 8

    def _draw_image(self, rec, side, width, pad, y):
        photo = rec["photo"]
        if photo is not None:
            self._photos.append(photo)
            w, h = photo.width(), photo.height()
        else:
            w, h = 240, 84
        left = width - pad - w if side == "out" else pad
        round_rect(self, left - 3, y - 3, left + w + 3, y + h + 3, 20,
                   fill=T.BLUE if side == "out" else T.BUBBLE_IN, outline="")
        if photo is not None:
            self.create_image(left, y, image=photo, anchor="nw")
        else:
            self.create_text(left + w / 2, y + h / 2, text=(rec["text"] or "image") + "\n(preview unavailable)",
                             fill=T.TEXT, font=self.small_font, justify="center")
        return y + h + 11
