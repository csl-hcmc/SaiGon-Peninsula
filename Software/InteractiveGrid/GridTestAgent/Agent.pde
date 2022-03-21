class Agent {
  float x;
  float y;

  float tam;

  int type;
  color colorType;
  boolean active;

  Agent(int type) {
    x = 0;
    y = 0;
    tam = 10;
    this.type = type;
    colorType = getAgentTypeColor(type );
    active = true;
  }

  void draw(PGraphics p) {
    p.ellipse(x, y, tam, tam);
  }

  void updatePos(float x, float y) {
    this.x = x;
    this.y = y;
  }
 
  
}
