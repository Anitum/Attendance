nohup tar cvf ~/attendance_v1.tar \
    --exclude='*.mkv' \
    --exclude='/home/ubuntu/PushToAWSandGrey' \
    --exclude='/home/ubuntu/faceDetectionTrack' \
    --exclude='/home/ubuntu/faceDetections' \
    --exclude='/home/ubuntu/faceDetections90' \
    --exclude='/home/ubuntu/faceDetectionsOld' \
    ~ &
