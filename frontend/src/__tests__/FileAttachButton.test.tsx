import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import FileAttachButton from "../components/FileAttachButton";

describe("FileAttachButton", () => {
  it("renders attach button", () => {
    render(<FileAttachButton onFileSelect={vi.fn()} />);
    expect(screen.getByLabelText("Attach file")).toBeInTheDocument();
  });

  it("opens file picker on click", () => {
    render(<FileAttachButton onFileSelect={vi.fn()} />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");
    fireEvent.click(screen.getByLabelText("Attach file"));
    expect(clickSpy).toHaveBeenCalled();
  });

  it("calls onFileSelect when file chosen", () => {
    const onFileSelect = vi.fn();
    render(<FileAttachButton onFileSelect={onFileSelect} />);
    const input = screen.getByTestId("file-input");
    const file = new File(["test"], "receipt.jpg", { type: "image/jpeg" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFileSelect).toHaveBeenCalledWith(file);
  });

  it("is disabled when disabled prop is true", () => {
    render(<FileAttachButton onFileSelect={vi.fn()} disabled />);
    expect(screen.getByLabelText("Attach file")).toBeDisabled();
  });

  it("accepts expected file types", () => {
    render(<FileAttachButton onFileSelect={vi.fn()} />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    expect(input.accept).toContain(".jpg");
    expect(input.accept).toContain(".pdf");
    expect(input.accept).toContain(".csv");
  });
});
