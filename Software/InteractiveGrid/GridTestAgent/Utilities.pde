//Agent types
color getAgentTypeColor(int type) {
  color c = color(0);
  if (type == 0) { //default type
    c = color(0, 100, 100);
  }
  if (type ==1) { //bikes
    c = color(0, 200, 150);
  }
  if (type ==2) { //people
    c = color(100, 0, 150);
  }
  if (type ==3) { //cars
    c = color(100, 100, 0);
  }
  if (type ==4) { //motorbikes
    c = color(100, 120, 150);
  }
  return  c;
}
