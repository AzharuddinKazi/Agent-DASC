# Frontend Testing Specification (Next.js)

## Framework
- **Unit / Component tests:** Vitest + React Testing Library
- **E2E:** Playwright (smoke tests only — not in PR gate, nightly only)
- **Storybook:** Component isolation for UI review (not automated — developer tool)

## Vitest config (`frontend/vitest.config.ts`)
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      thresholds: { lines: 75, functions: 75, branches: 70 },
    },
  },
});
```

## Test Setup (`frontend/tests/setup.ts`)
```ts
import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock Clerk
vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({ user: { id: "test-user", email: "test@example.com" } }),
  useAuth: () => ({ getToken: async () => "mock-jwt-token" }),
  SignedIn: ({ children }: any) => children,
  SignedOut: () => null,
  ClerkProvider: ({ children }: any) => children,
}));
```

---

## Component Tests

### Analysis Session — `tests/components/AnalysisSession.test.tsx`

```ts
describe("AnalysisSession", () => {
  test("renders query text and 'active' status badge on mount", () => {
    render(<AnalysisSession session={mockSession({ status: "active", user_query: "What is Q3 revenue?" })} />);
    expect(screen.getByText("What is Q3 revenue?")).toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveTextContent("active");
  });

  test("shows spinner when status is 'active'", () => {
    render(<AnalysisSession session={mockSession({ status: "active" })} />);
    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
  });

  test("shows 'completed' badge when status is completed", () => {
    render(<AnalysisSession session={mockSession({ status: "completed" })} />);
    expect(screen.queryByTestId("loading-spinner")).not.toBeInTheDocument();
    expect(screen.getByTestId("status-badge")).toHaveTextContent("completed");
  });

  test("renders pending checkpoint UI when pending_checkpoint is present", () => {
    const session = mockSession({
      pending_checkpoint: { checkpoint_type: "plan_approval", payload: { first_step: "Load orders table" } }
    });
    render(<AnalysisSession session={session} />);
    expect(screen.getByTestId("checkpoint-panel")).toBeInTheDocument();
    expect(screen.getByText(/Load orders table/i)).toBeInTheDocument();
  });

  test("approve button calls checkpoint API with action=approve", async () => {
    const mockPost = vi.fn().mockResolvedValue({ ok: true });
    vi.mocked(fetch).mockImplementation(mockPost);
    const session = mockSession({
      pending_checkpoint: { checkpoint_type: "plan_approval", payload: {} }
    });
    render(<AnalysisSession session={session} />);
    await userEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(mockPost).toHaveBeenCalledWith(
      expect.stringContaining("/checkpoint"),
      expect.objectContaining({ method: "POST", body: expect.stringContaining('"action":"approve"') })
    );
  });

  test("reject button shows confirmation dialog before calling API", async () => {
    render(<AnalysisSession session={mockSessionWithCheckpoint("plan_approval")} />);
    await userEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
  });
});
```

---

### Checkpoint Panel — `tests/components/CheckpointPanel.test.tsx`

```ts
describe("CheckpointPanel", () => {
  test("plan_approval: shows first_step text", () => {
    render(<CheckpointPanel
      type="plan_approval"
      payload={{ first_step: "Load the test_orders table" }}
      onAction={vi.fn()}
    />);
    expect(screen.getByText("Load the test_orders table")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });

  test("force_exit: shows hint input field and submit button", () => {
    render(<CheckpointPanel
      type="force_exit"
      payload={{ iteration: 5, max_iterations: 5, last_result: "Empty result" }}
      onAction={vi.fn()}
    />);
    expect(screen.getByRole("textbox", { name: /hint/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit hint/i })).toBeInTheDocument();
  });

  test("force_exit: submit hint disabled when hint field is empty", async () => {
    render(<CheckpointPanel type="force_exit" payload={{ iteration: 5 }} onAction={vi.fn()} />);
    expect(screen.getByRole("button", { name: /submit hint/i })).toBeDisabled();
    await userEvent.type(screen.getByRole("textbox"), "Use net_amount");
    expect(screen.getByRole("button", { name: /submit hint/i })).not.toBeDisabled();
  });

  test("result_confirmation: shows the result text and code snippet", () => {
    render(<CheckpointPanel
      type="result_confirmation"
      payload={{ result: "Total: $1,649.83", code: "import pandas as pd" }}
      onAction={vi.fn()}
    />);
    expect(screen.getByText(/\$1,649.83/)).toBeInTheDocument();
    expect(screen.getByText(/import pandas/)).toBeInTheDocument();
  });

  test("report_approval: shows export PDF button for DSSTAR+ mode", () => {
    render(<CheckpointPanel
      type="report_approval"
      payload={{ mode: "plus", available_actions: ["save", "export_pdf", "refine", "discard"] }}
      onAction={vi.fn()}
    />);
    expect(screen.getByRole("button", { name: /export pdf/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refine/i })).toBeInTheDocument();
  });

  test("report_approval: does NOT show export PDF button for base mode", () => {
    render(<CheckpointPanel
      type="report_approval"
      payload={{ mode: "base", available_actions: ["save", "discard"] }}
      onAction={vi.fn()}
    />);
    expect(screen.queryByRole("button", { name: /export pdf/i })).not.toBeInTheDocument();
  });
});
```

---

### Agent Activity Feed — `tests/components/ActivityFeed.test.tsx`

```ts
describe("ActivityFeed", () => {
  test("renders agent step names in order", () => {
    const steps = [
      mockStep({ agent_name: "analyzer", status: "completed" }),
      mockStep({ agent_name: "planner", status: "completed" }),
      mockStep({ agent_name: "coder", status: "active" }),
    ];
    render(<ActivityFeed steps={steps} />);
    const items = screen.getAllByTestId("activity-item");
    expect(items[0]).toHaveTextContent("analyzer");
    expect(items[1]).toHaveTextContent("planner");
    expect(items[2]).toHaveTextContent("coder");
  });

  test("active step shows a spinning indicator", () => {
    render(<ActivityFeed steps={[mockStep({ agent_name: "coder", status: "active" })]} />);
    expect(screen.getByTestId("step-spinner")).toBeInTheDocument();
  });

  test("failed step shows error icon and message", () => {
    render(<ActivityFeed steps={[mockStep({ agent_name: "coder", status: "failed", error_message: "NameError" })]} />);
    expect(screen.getByTestId("step-error-icon")).toBeInTheDocument();
    expect(screen.getByText(/NameError/)).toBeInTheDocument();
  });

  test("collapsed feed shows only the most recent 3 steps by default", () => {
    const steps = Array.from({ length: 6 }, (_, i) =>
      mockStep({ agent_name: `step_${i}`, status: "completed" })
    );
    render(<ActivityFeed steps={steps} />);
    expect(screen.getAllByTestId("activity-item")).toHaveLength(3);
    expect(screen.getByRole("button", { name: /show all/i })).toBeInTheDocument();
  });

  test("show all button expands to all steps", async () => {
    const steps = Array.from({ length: 6 }, (_, i) =>
      mockStep({ agent_name: `step_${i}`, status: "completed" })
    );
    render(<ActivityFeed steps={steps} />);
    await userEvent.click(screen.getByRole("button", { name: /show all/i }));
    expect(screen.getAllByTestId("activity-item")).toHaveLength(6);
  });
});
```

---

### Knowledge Base Page — `tests/components/KnowledgePage.test.tsx`

```ts
describe("KnowledgePage", () => {
  test("upload button opens file picker", async () => {
    render(<KnowledgePage documents={[]} />);
    const btn = screen.getByRole("button", { name: /upload document/i });
    expect(btn).toBeInTheDocument();
  });

  test("shows pending status badge for document being indexed", () => {
    const docs = [mockDocument({ graphrag_status: "indexing", title: "Sales Report.pdf" })];
    render(<KnowledgePage documents={docs} />);
    expect(screen.getByTestId("doc-status-badge")).toHaveTextContent("indexing");
  });

  test("shows community count after indexing completes", () => {
    const docs = [mockDocument({ graphrag_status: "indexed", community_count: 5 })];
    render(<KnowledgePage documents={docs} />);
    expect(screen.getByText(/5 communities/i)).toBeInTheDocument();
  });

  test("cost warning modal appears before upload proceeds when threshold exceeded", async () => {
    const mockFile = new File(["content ".repeat(100000)], "large.pdf", { type: "application/pdf" });
    render(<KnowledgePage documents={[]} estimatedCost={7.50} costThreshold={5.00} />);
    const input = screen.getByTestId("file-input");
    await userEvent.upload(input, mockFile);
    expect(screen.getByRole("dialog", { name: /estimated cost/i })).toBeInTheDocument();
    expect(screen.getByText(/\$7\.50/)).toBeInTheDocument();
  });

  test("cost warning confirm proceeds with indexing", async () => {
    const mockUpload = vi.fn().mockResolvedValue({ ok: true });
    vi.mocked(fetch).mockImplementation(mockUpload);
    render(<KnowledgePage documents={[]} estimatedCost={7.50} costThreshold={5.00} />);
    // ... simulate upload and confirm
    await userEvent.click(screen.getByRole("button", { name: /proceed anyway/i }));
    expect(mockUpload).toHaveBeenCalled();
  });
});
```

---

### Catalog Page — `tests/components/CatalogPage.test.tsx`

```ts
describe("CatalogPage", () => {
  test("renders list of data sources", () => {
    const sources = [
      mockSource({ name: "Production MySQL", source_type: "mysql" }),
      mockSource({ name: "Sales CSV", source_type: "file" }),
    ];
    render(<CatalogPage sources={sources} />);
    expect(screen.getByText("Production MySQL")).toBeInTheDocument();
    expect(screen.getByText("Sales CSV")).toBeInTheDocument();
  });

  test("MySQL source shows table count badge", () => {
    render(<CatalogPage sources={[mockSource({ source_type: "mysql", table_count: 12 })]} />);
    expect(screen.getByText(/12 tables/i)).toBeInTheDocument();
  });

  test("test connection button fires API call and shows success", async () => {
    const mockTest = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
    vi.mocked(fetch).mockImplementation(mockTest);
    render(<CatalogPage sources={[mockSource({ source_type: "mysql" })]} />);
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));
    expect(await screen.findByText(/connection successful/i)).toBeInTheDocument();
  });

  test("test connection failure shows error message", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ success: false, message: "Access denied for user" })
    } as any);
    render(<CatalogPage sources={[mockSource({ source_type: "mysql" })]} />);
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));
    expect(await screen.findByText(/Access denied/i)).toBeInTheDocument();
  });

  test("password field in add-source modal is never shown in plain text", async () => {
    render(<CatalogPage sources={[]} />);
    await userEvent.click(screen.getByRole("button", { name: /add source/i }));
    const passwordInput = screen.getByLabelText(/password/i);
    expect(passwordInput).toHaveAttribute("type", "password");
  });
});
```

---

### Report View — `tests/components/ReportView.test.tsx`

```ts
describe("ReportView", () => {
  test("base mode shows plain text result, not HTML", () => {
    render(<ReportView report={mockReport({ mode: "base", final_result: "Total: $1,649.83", html_content: null })} />);
    expect(screen.getByText("Total: $1,649.83")).toBeInTheDocument();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  test("DSSTAR+ mode renders HTML content in an iframe or article", () => {
    render(<ReportView report={mockReport({
      mode: "plus",
      html_content: "<h1>Q3 Analysis</h1><p>Revenue grew by 15%.</p>"
    })} />);
    // HTML report is rendered in a sandboxed iframe
    const iframe = screen.getByTitle(/report/i);
    expect(iframe).toBeInTheDocument();
  });

  test("export PDF button is visible for DSSTAR+ reports", () => {
    render(<ReportView report={mockReport({ mode: "plus", html_content: "<h1>Report</h1>" })} />);
    expect(screen.getByRole("button", { name: /export pdf/i })).toBeInTheDocument();
  });

  test("export PDF button is NOT shown for base reports", () => {
    render(<ReportView report={mockReport({ mode: "base", final_result: "Total: $100" })} />);
    expect(screen.queryByRole("button", { name: /export pdf/i })).not.toBeInTheDocument();
  });

  test("refine button calls /reports/{id}/refine API", async () => {
    const mockRefine = vi.fn().mockResolvedValue({ ok: true });
    vi.mocked(fetch).mockImplementation(mockRefine);
    render(<ReportView report={mockReport({ id: "report-1", mode: "plus", html_content: "<h1>R</h1>" })} />);
    await userEvent.click(screen.getByRole("button", { name: /refine/i }));
    expect(mockRefine).toHaveBeenCalledWith(
      expect.stringContaining("/reports/report-1/refine"),
      expect.objectContaining({ method: "POST" })
    );
  });
});
```

---

### Session History — `tests/components/SessionList.test.tsx`

```ts
describe("SessionList", () => {
  test("renders session list with query text and status", () => {
    const sessions = [
      mockSession({ user_query: "Revenue Q3", status: "completed" }),
      mockSession({ user_query: "Customer churn", status: "active" }),
    ];
    render(<SessionList sessions={sessions} total={2} />);
    expect(screen.getByText("Revenue Q3")).toBeInTheDocument();
    expect(screen.getByText("Customer churn")).toBeInTheDocument();
  });

  test("search input filters sessions via API", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [mockSession({ user_query: "revenue" })], total: 1 })
    });
    vi.mocked(fetch).mockImplementation(mockFetch);
    render(<SessionList sessions={[]} total={0} />);
    await userEvent.type(screen.getByRole("searchbox"), "revenue");
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("q=revenue"),
      expect.anything()
    ));
  });

  test("clicking a session navigates to session detail page", async () => {
    const { push } = useRouter();
    render(<SessionList sessions={[mockSession({ id: "sess-1", user_query: "Q?" })]} total={1} />);
    await userEvent.click(screen.getByText("Q?"));
    expect(push).toHaveBeenCalledWith("/analyses/sess-1");
  });
});
```

---

## WebSocket Integration (Vitest + Mock WS)

### `tests/hooks/useSessionWebSocket.test.ts`

```ts
import { renderHook, act } from "@testing-library/react";
import WS from "jest-websocket-mock";

describe("useSessionWebSocket", () => {
  let server: WS;
  beforeEach(() => { server = new WS("ws://localhost/ws/analyses/sess-1"); });
  afterEach(() => WS.clean());

  test("connects on mount and disconnects on unmount", async () => {
    const { unmount } = renderHook(() => useSessionWebSocket("sess-1"));
    await server.connected;
    unmount();
    await server.closed;
  });

  test("agent_started event updates step list", async () => {
    const { result } = renderHook(() => useSessionWebSocket("sess-1"));
    await server.connected;
    act(() => {
      server.send(JSON.stringify({ event: "agent_started", data: { agent_name: "coder", step_number: 2 } }));
    });
    expect(result.current.steps).toHaveLength(1);
    expect(result.current.steps[0].agent_name).toBe("coder");
  });

  test("checkpoint_pending event sets pending_checkpoint state", async () => {
    const { result } = renderHook(() => useSessionWebSocket("sess-1"));
    await server.connected;
    act(() => {
      server.send(JSON.stringify({
        event: "checkpoint_pending",
        data: { checkpoint_type: "plan_approval", payload: { first_step: "Load orders" } }
      }));
    });
    expect(result.current.pendingCheckpoint?.checkpoint_type).toBe("plan_approval");
  });

  test("reconnects automatically after connection drop", async () => {
    renderHook(() => useSessionWebSocket("sess-1"));
    await server.connected;
    server.close();
    // Give reconnect delay to pass
    await new Promise(r => setTimeout(r, 2000));
    expect(server.server.clients().length).toBeGreaterThan(0);
  });
});
```

---

## Playwright E2E Smoke Tests (Nightly Only)

### `e2e/smoke.spec.ts`

```ts
import { test, expect } from "@playwright/test";

test.describe("Smoke: Auth + navigation", () => {
  test("login page loads", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
  });

  test("authenticated user lands on dashboard", async ({ page }) => {
    await signIn(page);  // uses Playwright auth fixtures
    await expect(page.url()).toContain("/dashboard");
  });
});

test.describe("Smoke: Create analysis", () => {
  test("can create a new analysis session", async ({ page }) => {
    await signIn(page);
    await page.goto("/analyses/new");
    await page.getByRole("textbox", { name: /question/i }).fill("What is the total revenue?");
    await page.getByRole("button", { name: /start analysis/i }).click();
    await expect(page.getByTestId("status-badge")).toHaveText("active");
  });
});

test.describe("Smoke: Catalog", () => {
  test("catalog page loads without errors", async ({ page }) => {
    await signIn(page);
    await page.goto("/catalog");
    await expect(page.getByRole("heading", { name: /data catalog/i })).toBeVisible();
  });
});

test.describe("Smoke: Knowledge base", () => {
  test("knowledge page loads", async ({ page }) => {
    await signIn(page);
    await page.goto("/knowledge");
    await expect(page.getByRole("heading", { name: /knowledge base/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /upload document/i })).toBeVisible();
  });
});
```

---

## GitHub Actions: Frontend CI

```yaml
# .github/workflows/frontend.yml
name: Frontend Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: "npm" }
      - run: npm ci
      - run: npm run type-check          # tsc --noEmit
      - run: npm run lint                # eslint + next lint
      - run: npm run test:coverage       # vitest run --coverage
      - uses: codecov/codecov-action@v4
        with: { files: ./coverage/lcov.info }
```

## Pre-commit: Frontend

Add to `.pre-commit-config.yaml`:
```yaml
  - repo: local
    hooks:
      - id: frontend-type-check
        name: TypeScript type check
        language: system
        entry: bash -c "cd frontend && npm run type-check"
        pass_filenames: false
        files: ^frontend/

      - id: frontend-lint
        name: ESLint
        language: system
        entry: bash -c "cd frontend && npm run lint"
        pass_filenames: false
        files: ^frontend/
```
