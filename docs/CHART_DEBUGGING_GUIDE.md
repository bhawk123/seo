# Chart Debugging Guide

## Current Status

✅ **Test chart page works** (`test_charts.html`)
❌ **Report charts don't work** (`crawls/pinsandaces.com/latest/report.html`)

## Debugging Steps

### Step 1: Open the Report and Check Browser Console

```bash
open crawls/pinsandaces.com/latest/report.html
```

Then open Browser Console (F12 or Cmd+Option+I on Mac)

### Step 2: Look for These Console Messages

You should see messages like:
```
[INIT] Script loaded, Chart.js status: ...
[SUCCESS] Chart.js loaded, version: ...
[CHARTS] Initializing charts...
[CHARTS] DOM ready state: ...
[CHARTS] Found X canvas elements total
[CHARTS] Attempting to create radar chart...
[CHARTS] Radar canvas element: ...
```

### Step 3: Identify the Problem

#### Problem A: Chart.js Not Loading
If you see:
```
[ERROR] Chart.js failed to load from CDN
```

**Solution:**
- Check internet connection
- Disable ad blockers
- Check if CDN is blocked by firewall/network
- Try different network

#### Problem B: Canvas Elements Not Found
If you see:
```
[CHARTS] Found 0 canvas elements total
[CHARTS] Radar canvas element: null
```

**Solution:**
- The canvas elements aren't in the DOM
- Check if you're on the right tab (Tab 1: Overview)
- Look at HTML source to verify canvas elements exist

#### Problem C: JavaScript Error
If you see:
```
[CHARTS] ✗ Error creating radar chart: [error message]
```

**Solution:**
- Read the error message carefully
- Common issues:
  - Invalid data values (NaN, undefined)
  - Chart.js API changed
  - Browser compatibility issue

#### Problem D: Charts in Wrong Tab
The canvas elements are in different tabs:
- Tab 1 (Overview): radarChart, issueChart
- Tab 3 (Content Quality): readabilityChart
- Tab 4 (Security & Mobile): scoresChart

**Solution:**
- Make sure you're looking at Tab 1 first
- Click through all tabs to see which have charts

### Step 4: Compare with Test Page

Open both files side-by-side:
```bash
# Terminal 1
open test_charts.html

# Terminal 2
open crawls/pinsandaces.com/latest/report.html
```

Check console in both. If test page works but report doesn't, the issue is:
1. **CDN loading timing** - Report script runs before Chart.js loads
2. **DOM structure** - Canvas elements hidden or in inactive tabs
3. **JavaScript conflict** - Some other code interfering

### Step 5: Manual Test in Console

Once report is open, paste this in browser console:

```javascript
// Check Chart.js
console.log('Chart:', typeof Chart);
console.log('Version:', Chart?.version);

// Check canvas elements
console.log('Radar canvas:', document.getElementById('radarChart'));
console.log('Issue canvas:', document.getElementById('issueChart'));
console.log('All canvas:', document.querySelectorAll('canvas'));

// Try to create a simple chart manually
const testCanvas = document.getElementById('radarChart');
if (testCanvas && typeof Chart !== 'undefined') {
    try {
        new Chart(testCanvas, {
            type: 'bar',
            data: {
                labels: ['Test'],
                datasets: [{
                    label: 'Manual Test',
                    data: [100]
                }]
            }
        });
        console.log('✓ Manual chart creation WORKED!');
    } catch (e) {
        console.error('✗ Manual chart creation FAILED:', e);
    }
} else {
    console.log('Canvas or Chart.js not available');
}
```

### Step 6: Check Tab Display

The tabs use CSS to show/hide content. Check if canvas is hidden:

```javascript
// In browser console
const radar = document.getElementById('radarChart');
console.log('Radar visibility:', window.getComputedStyle(radar.parentElement.parentElement).display);
```

If it shows `display: none`, the tab isn't active. Click "Overview" tab first.

## Quick Fix Options

### Option 1: Inline Chart.js (No CDN)

Download Chart.js and include it directly in the report:

```bash
# Download Chart.js
curl -o templates/chart.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js
```

Then update template:
```html
<script src="chart.min.js"></script>
```

### Option 2: Use Different CDN

Try unpkg instead of jsdelivr:
```html
<script src="https://unpkg.com/chart.js@4.4.1/dist/chart.umd.min.js"></script>
```

### Option 3: Delay Chart Initialization

Add a longer delay:
```javascript
setTimeout(function() {
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }
}, 2000); // Wait 2 seconds
```

### Option 4: Force Charts to Initialize on Tab Click

Add event listeners to initialize when tab is clicked:
```javascript
document.querySelector('label[for="tab1"]').addEventListener('click', function() {
    setTimeout(initializeCharts, 100);
});
```

## Common Issues and Solutions

### Issue: "Chart is not defined"
- Chart.js didn't load from CDN
- Network blocking CDN
- Ad blocker removing script

**Fix:** Download and host Chart.js locally

### Issue: "Cannot read properties of null (reading 'getContext')"
- Canvas element doesn't exist in DOM
- Canvas is in hidden tab

**Fix:** Make sure you're on the right tab, or initialize charts when tabs are clicked

### Issue: Charts render but are invisible
- Canvas has width/height of 0
- Parent container is hidden
- CSS display: none on parent

**Fix:** Check CSS, make sure parent container has dimensions

### Issue: Charts render in test page but not report
- Timing issue - charts trying to initialize before DOM ready
- Tab system hiding canvas elements
- Script loading order

**Fix:** Initialize charts on tab click, not on page load

## Next Steps

After identifying the issue with console debugging:

1. **Report what you see** in console
2. **Take screenshot** of console messages
3. **Try manual chart creation** in console
4. **Check which tabs** actually have visible canvas elements

Then we can apply the specific fix needed.
