

void agentsSendPos(){
    // println("seding UDP");
    String ip       = "localhost";  // the remote IP address
    int port        = 15810;    // the destination port
    
    String agentsPos = agents.getStrPos();

    // send the message
    udp.send( agentsPos, ip, port );
    //println(msg); 
}
