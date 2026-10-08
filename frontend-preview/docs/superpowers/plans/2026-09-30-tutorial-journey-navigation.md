# Tutorial Journey Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a silent visual preparation progress bar and one consistent “上一步” control throughout the tutorial journey.

**Architecture:** Replace the text-heavy `JourneyProgress` presentation with a reusable progressbar that accepts a percentage. Extend the shared `Page` wrapper with explicit `backTo` and `progress` props, while the two custom-layout pages render the same shared navigation component directly.

**Tech Stack:** React 19, React Router, TypeScript, CSS.

---

### Task 1: Shared journey controls

**Files:**
- Modify: `src/components/tutorial/JourneyProgress.tsx`
- Create: `src/components/tutorial/JourneyNavigation.tsx`
- Modify: `src/components/layout/Page.tsx`
- Modify: `src/styles.css`

- [x] Replace the visible stage list and note with a semantic progressbar whose only visible state is the filled track.
- [x] Add a tertiary “上一步” link using the existing button component and a left arrow icon.
- [x] Add optional `backTo` and `progress` props to `Page` and render the shared controls above the title.
- [x] Style the controls as a thin black/cool-gray bar with existing focus, hover, and mobile behavior.

### Task 2: Connect every tutorial page

**Files:**
- Modify: `src/pages/TutorialInput.tsx`
- Modify: `src/pages/Parsing.tsx`
- Modify: `src/pages/Recipe.tsx`
- Modify: `src/pages/BeautyKit.tsx`
- Modify: `src/pages/Matching.tsx`
- Modify: `src/pages/FaceScan.tsx`
- Modify: `src/pages/BeautyProfile.tsx`
- Modify: `src/pages/MyTutorial.tsx`
- Modify: `src/pages/LiveCoach.tsx`
- Modify: `src/pages/Finish.tsx`

- [x] Assign progress values of 0%, 25%, 50%, 75%, and 100% at completed journey milestones.
- [x] Assign deterministic previous routes, including the product-mode branch before Face Scan.
- [x] Remove the previous visible progress labels and notes.

### Task 3: Verify

**Files:**
- Test: `tests/*.test.mjs`

- [x] Run `npm test` and expect all non-live tests to pass.
- [x] Run `npm run build` and expect the production build to complete.
- [x] Check desktop and mobile layouts in the running Vite preview and confirm that the bar has no visible text and the only added action is “上一步”.
