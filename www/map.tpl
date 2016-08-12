<!DOCTYPE html>
<html>
  <head>
    <title>SaveThePeaches Map INTA</title>
    <meta name="viewport" content="initial-scale=1.0">
    <meta charset="utf-8">
    <link rel="stylesheet" type="text/css" href="style.css" />
    <link rel="stylesheet" href="//code.jquery.com/ui/1.11.4/themes/smoothness/jquery-ui.css">
    <link rel="stylesheet" type="text/css" href="jquery.ui.timepicker.css" />
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.12.0/jquery.min.js"></script>
    <script src="//code.jquery.com/ui/1.11.4/jquery-ui.js"></script>
    <script type="text/javascript" src="map.js"></script>
    <script type="text/javascript" src="jquery.ui.timepicker.js"></script>
    <script src="https://maps.googleapis.com/maps/api/js?key=AIzaSyB8M8hxvNymZavj2R3hkN5ERfbBLp9c3J8&callback=initMap&libraries=geometry" async defer></script>
  </head>
  <body>
    <div id="map"></div>
    <div id="control_panel">
      <input type="text" id="datepicker"><br>
      <input type="text" id="timepicker"><br>
      <button id="prev_time"><<</button>
      <button id="dateselect" onclick="load_data(0)">Load</button>
      <button id="next_time">>></button>
      <br><br>
      <button id="metric_rssi" onclick="$('#metric').val('rssi'); load_data();">RSSI</button>
      <button id="metric_pdr" onclick="$('#metric').val('pdr'); load_data();">PDR</button>
      <input type="hidden" id="metric" value="pdr">
      <input type="hidden" id="sitename" value={{sitename}}>
    </div>
    <div id="links">
      <a href="https://sol.paris.inria.fr/" target="_blank"><img src="grafana.png"></a>
    </div>
  </body>
</html>

