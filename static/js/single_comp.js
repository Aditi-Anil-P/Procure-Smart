const toolbarHTML = `
  <label>Select Parameter</label>
  <select class="form-select">
    <option>Revenue</option>
    <option>Profit</option>
    <option>Employee Count</option>
  </select>

  <label>Preference</label>
  <div class="btn-group" role="group">
    <button class="btn btn-outline-info">Prefer Higher Value</button>
    <button class="btn btn-outline-info">Prefer Lower Value</button>
  </div>

  <label>Min Value</label>
  <input type="number" class="form-control" placeholder="e.g. 10">

  <label>Max Value</label>
  <input type="number" class="form-control" placeholder="e.g. 1000">

  <label>Number of Companies</label>
  <input type="number" class="form-control" min="1" max="25" placeholder="Max 25">
`;

// Render toolbars
document.getElementById('toolbar-top').innerHTML = toolbarHTML;
document.getElementById('toolbar-sidebar').innerHTML = toolbarHTML;

// Render placeholder charts
const ctx1 = document.getElementById('scatterPlot').getContext('2d');
new Chart(ctx1, {
  type: 'scatter',
  data: {
    datasets: [{
      label: 'Companies',
      data: [{x:10,y:20},{x:15,y:25},{x:20,y:30}],
      backgroundColor: '#00ffff'
    }]
  },
  options: {
    responsive: true,
    plugins: {
      legend: {display: false}
    }
  }
});

const ctx2 = document.getElementById('barChart').getContext('2d');
new Chart(ctx2, {
  type: 'bar',
  data: {
    labels: ['Company A', 'Company B', 'Company C'],
    datasets: [{
      label: 'Parameter',
      data: [75, 88, 64],
      backgroundColor: '#00ffff'
    }]
  },
  options: {
    responsive: true
  }
});

function downloadChart(id) {
  const canvas = document.getElementById(id);
  const link = document.createElement('a');
  link.download = `${id}.png`;
  link.href = canvas.toDataURL();
  link.click();
}

function expandChart(id) {
  const canvas = document.getElementById(id);
  canvas.requestFullscreen();
}