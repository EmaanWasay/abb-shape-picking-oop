MODULE MainModule

    ! =================================================================
    ! STATION DATA - everything taught on this bench is in this section.
    ! On a new bench: re-teach tsuc, white, empty, pHome, pApproach and
    ! the 5 place targets, then check PICK_Z (and the marker position on the Pi).
    ! =================================================================

    ! ----- Tool and the two work objects -----
    TASK PERS tooldata tsuc:=[TRUE,[[-90.0441,1.4018,177.644],[1,0,0,0]],[0.5,[50,0,50],[1,0,0,0],0,0,0]];
    ! white = the A3 sheet: origin on a corner, X along the 297 mm edge, Y along the 420 mm edge
    TASK PERS wobjdata white:=[FALSE,TRUE,"",[[446.109,-300.614,-2.32287],[0.999983,0.00142333,0.00155486,0.00552666]],[[0,0,0],[1,0,0,0]]];
    ! empty = the placing jig
    TASK PERS wobjdata empty:=[FALSE,TRUE,"",[[531.086,163.485,5.75979],[0.999955,-0.00810186,-0.00485621,-3.74937E-05]],[[0,0,0],[1,0,0,0]]];

    ! ----- Taught positions: home + approach + 5 slots = 7 -----
    ! pHome and pApproach are taught in white. The 5 slots are taught in empty.
    CONST robtarget pHome:=[[-55.28,63.54,315.34],[0.00112561,-0.0675342,-0.997712,0.00299435],[0,-1,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    ! pApproach = the waiting position beside the sheet. The robot starts here,
    ! passes through here between the sheet and the jig, and returns here after
    ! every place. It also gives its orientation to every computed pick point.
    CONST robtarget pApproach:=[[-84.00,104.10,213.03],[0.00113286,-0.0675324,-0.997712,0.00300615],[0,-1,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget ptriangle:=[[34.19,50.21,0.68],[0.000283379,-0.137896,-0.990442,0.00310788],[0,-1,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pcircle:=[[149.94,170.74,2.16],[0.000287709,-0.137903,-0.990441,0.00311737],[0,-1,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget psquare:=[[145.20,40.81,0.61],[0.000287143,-0.137885,-0.990443,0.0031159],[0,-1,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pHexagon:=[[41.70,159.07,0.58],[0.00114653,-0.0675225,-0.997713,0.00300988],[0,-1,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pStar:=[[90.56,100.18,0.58],[0.00113708,-0.0675337,-0.997712,0.00301377],[0,-1,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];

    ! ----- Pick height (in white) -----
    ! The Raspberry Pi sends X and Y in work object white. The marker position
    ! used for that is in picker/config.py on the Pi (marker_x_mm, marker_y_mm).
    CONST num PICK_Z:=6;

    ! ----- Safety fence: the A3 sheet plus 15 mm margin (in white) -----
    CONST num SHEET_MIN_X:=-15;
    CONST num SHEET_MAX_X:=312;
    CONST num SHEET_MIN_Y:=-15;
    CONST num SHEET_MAX_Y:=435;

    ! ----- Motion settings -----
    ! SAFE_HEIGHT: height above a pick or place point where travel moves end
    ! APPROACH_HEIGHT: the last part of the way down is done slowly
    CONST num SAFE_HEIGHT:=100;
    CONST num APPROACH_HEIGHT:=20;
    CONST num GRIP_TIME:=0.5;
    CONST num RELEASE_TIME:=0.5;
    CONST speeddata vTravel:=v200;
    CONST speeddata vApproach:=v50;

    ! ----- Placing corrections (in empty) -----
    ! Shift for ALL place positions, in mm. -Y = left as seen from the operator side.
    ! If it moves the wrong way, change -7 to 7 (or move the value to X).
    CONST num PLACE_SHIFT_X:=0;
    CONST num PLACE_SHIFT_Y:=-7;
    ! Extra wrist turn at the slot, in degrees, added to the camera's angle.
    ! Negative = anticlockwise seen from above (the tool Z points down).
    ! Tune between -2 and -5. If it turns the wrong way, make it positive.
    CONST num TRIANGLE_ROT_FIX:=-3.5;
    CONST num SQUARE_ROT_FIX:=-3.5;

    ! =================================================================
    ! VARIABLES
    ! =================================================================
    VAR string Server_message:="";
    VAR string client_message:="";
    VAR num nX:=0;
    VAR num nY:=0;
    VAR num nShapeID:=0;
    VAR num nAngle:=0;


    ! =================================================================
    ! MAIN
    ! =================================================================
    PROC main()
        Reset doValve1;

        ! Computed pick points have no taught arm posture, so let the
        ! controller choose the nearest one. Fixes error 50436.
        ConfL\Off;
        ConfJ\Off;
        SingArea\Wrist;

        MoveJ pHome, vTravel, fine, tsuc\WObj:=white;
        MoveJ pApproach, vTravel, fine, tsuc\WObj:=white;
        TPWrite "=== Pick and Place (Vision) ===";

        RobotAsClientConnect;
        TPWrite "Connected to server.";

        WHILE TRUE DO
            ! Tell the server we are ready (robot is waiting at pApproach)
            client_message:="ready";
            RobotClienSendMessage client_message;

            ! Receive "x,y,shapeID,angle" or "quit"
            Server_message:=RobotClientReciveMessage();
            TPWrite "Server says: "+Server_message;

            IF Server_message="quit" THEN
                TPWrite "Quitting.";
                MoveJ pHome, vTravel, fine, tsuc\WObj:=white;
                RobotClientCloseAndDisconnect;
                RETURN;
            ENDIF

            IF Server_message="error" THEN
                TPWrite "Server error. Waiting for the next command...";
            ELSEIF ParseMessage(Server_message)=0 THEN
                TPWrite "Could not read the message.";
                client_message:="error";
                RobotClienSendMessage client_message;
            ELSEIF nShapeID<1 OR nShapeID>5 THEN
                TPWrite "Unknown shape ID: "+ValToStr(nShapeID);
                client_message:="error";
                RobotClienSendMessage client_message;
            ELSEIF NOT OnTheSheet(nX,nY) THEN
                TPWrite "Refused - position is off the sheet.";
                client_message:="error";
                RobotClienSendMessage client_message;
            ELSE
                TPWrite "X="+ValToStr(nX)+" Y="+ValToStr(nY)+" Shape="+ValToStr(nShapeID)+" Ang="+ValToStr(nAngle);

                ! Wait for yellow button before picking
                TPWrite "Press yellow button to pick...";
                WaitDI diOkButton, 1;

                PickShape PickTarget(nX, nY);
                PlaceShape GetTarget(nShapeID), nAngle+PlaceRotFix(nShapeID);

                client_message:="done";
                RobotClienSendMessage client_message;
                TPWrite "Placed. Waiting for the next shape...";
            ENDIF
        ENDWHILE
    ENDPROC


    ! =================================================================
    ! FUNC - Parse "x,y,shapeID,angle"
    ! Returns 1 if all four values were read, otherwise 0
    ! =================================================================
    FUNC num ParseMessage(string sMsg)
        VAR num nLen;
        VAR num nPos1;
        VAR num nPos2;
        VAR num nPos3;
        VAR string sPart1;
        VAR string sPart2;
        VAR string sPart3;
        VAR string sPart4;
        VAR bool bOk1;
        VAR bool bOk2;
        VAR bool bOk3;
        VAR bool bOk4;

        nLen:=StrLen(sMsg);

        nPos1:=StrFind(sMsg, 1, ",");
        IF nPos1>nLen THEN
            RETURN 0;
        ENDIF

        nPos2:=StrFind(sMsg, nPos1+1, ",");
        IF nPos2>nLen THEN
            RETURN 0;
        ENDIF

        nPos3:=StrFind(sMsg, nPos2+1, ",");
        IF nPos3>nLen THEN
            RETURN 0;
        ENDIF

        sPart1:=StrPart(sMsg, 1, nPos1-1);
        sPart2:=StrPart(sMsg, nPos1+1, nPos2-nPos1-1);
        sPart3:=StrPart(sMsg, nPos2+1, nPos3-nPos2-1);
        sPart4:=StrPart(sMsg, nPos3+1, nLen-nPos3);

        bOk1:=StrToVal(sPart1, nX);
        bOk2:=StrToVal(sPart2, nY);
        bOk3:=StrToVal(sPart3, nShapeID);
        bOk4:=StrToVal(sPart4, nAngle);

        IF bOk1 AND bOk2 AND bOk3 AND bOk4 THEN
            RETURN 1;
        ELSE
            RETURN 0;
        ENDIF
    ENDFUNC


    ! =================================================================
    ! FUNC - Safety fence: is this point on the A3 sheet?
    ! =================================================================
    FUNC bool OnTheSheet(num x, num y)
        RETURN x>=SHEET_MIN_X AND x<=SHEET_MAX_X AND y>=SHEET_MIN_Y AND y<=SHEET_MAX_Y;
    ENDFUNC


    ! =================================================================
    ! FUNC - Pick point from the position the Pi sends (in white)
    ! Copies pApproach (orientation and arm posture) and changes only X, Y, Z
    ! =================================================================
    FUNC robtarget PickTarget(num x, num y)
        VAR robtarget p;

        p:=pApproach;
        p.trans.x:=x;
        p.trans.y:=y;
        p.trans.z:=PICK_Z;
        RETURN p;
    ENDFUNC


    ! =================================================================
    ! FUNC - Fixed place slot by shape ID
    ! 1=triangle, 2=circle, 3=square, 4=hexagon, 5=star
    ! =================================================================
    FUNC robtarget GetTarget(num nShape)
        IF nShape=1 THEN
            RETURN ptriangle;
        ELSEIF nShape=2 THEN
            RETURN pcircle;
        ELSEIF nShape=3 THEN
            RETURN psquare;
        ELSEIF nShape=4 THEN
            RETURN pHexagon;
        ELSE
            RETURN pStar;
        ENDIF
    ENDFUNC


    ! =================================================================
    ! FUNC - Extra wrist turn at the slot for each shape (degrees)
    ! =================================================================
    FUNC num PlaceRotFix(num nShape)
        IF nShape=1 THEN
            RETURN TRIANGLE_ROT_FIX;
        ELSEIF nShape=3 THEN
            RETURN SQUARE_ROT_FIX;
        ELSE
            RETURN 0;
        ENDIF
    ENDFUNC


    ! =================================================================
    ! PROC - Pick from the sheet (white work object)
    ! Starts and ends at pApproach. Goes straight down and straight up.
    ! =================================================================
    PROC PickShape(robtarget pPick)
        TPWrite "Picking...";
        MoveJ pApproach, vTravel, fine, tsuc\WObj:=white;

        ! Above the shape, then straight down (slow for the last 20 mm)
        MoveJ Offs(pPick, 0, 0, SAFE_HEIGHT), vTravel, fine, tsuc\WObj:=white;
        MoveL Offs(pPick, 0, 0, APPROACH_HEIGHT), vTravel, fine, tsuc\WObj:=white;
        MoveL pPick, vApproach, fine, tsuc\WObj:=white;

        ! Suction on
        Set doValve1;
        WaitTime GRIP_TIME;

        ! Straight up, then back to the waiting position beside the sheet
        MoveL Offs(pPick, 0, 0, APPROACH_HEIGHT), vApproach, fine, tsuc\WObj:=white;
        MoveL Offs(pPick, 0, 0, SAFE_HEIGHT), vTravel, fine, tsuc\WObj:=white;
        MoveJ pApproach, vTravel, fine, tsuc\WObj:=white;
    ENDPROC


    ! =================================================================
    ! PROC - Place in the fixed slot (empty work object) with rotation
    ! Starts and ends at pApproach. Goes straight down and straight up.
    ! =================================================================
    PROC PlaceShape(robtarget pSlot, num nRotation)
        VAR robtarget pPlace;

        TPWrite "Placing with rotation "+ValToStr(nRotation)+" deg...";

        ! Shift the slot position, then turn the wrist about the tool's Z axis
        pPlace:=RelTool(Offs(pSlot, PLACE_SHIFT_X, PLACE_SHIFT_Y, 0), 0, 0, 0\Rz:=nRotation);

        ! Above the slot, then straight down (slow for the last 20 mm)
        MoveJ Offs(pPlace, 0, 0, SAFE_HEIGHT), vTravel, fine, tsuc\WObj:=empty;
        MoveL Offs(pPlace, 0, 0, APPROACH_HEIGHT), vTravel, fine, tsuc\WObj:=empty;
        MoveL pPlace, vApproach, fine, tsuc\WObj:=empty;

        ! Suction off
        Reset doValve1;
        WaitTime RELEASE_TIME;

        ! Straight up, then back to the waiting position beside the sheet
        MoveL Offs(pPlace, 0, 0, APPROACH_HEIGHT), vApproach, fine, tsuc\WObj:=empty;
        MoveL Offs(pPlace, 0, 0, SAFE_HEIGHT), vTravel, fine, tsuc\WObj:=empty;
        MoveJ pApproach, vTravel, fine, tsuc\WObj:=white;
    ENDPROC


    ! =================================================================
    ! PROC - Recovery: lift 50 mm straight up, then go home
    ! Run with: Debug -> PP to Routine -> GoHome
    ! =================================================================
    PROC GoHome()
        VAR robtarget pNow;

        ConfL\Off;
        ConfJ\Off;
        ! Lift straight up from wherever the robot is
        pNow:=CRobT(\Tool:=tsuc\WObj:=wobj0);
        MoveL Offs(pNow, 0, 0, 50), v50, fine, tsuc\WObj:=wobj0;
        ! Then go home
        MoveJ pHome, v100, fine, tsuc\WObj:=white;
        TPWrite "Robot is home.";
    ENDPROC

ENDMODULE
