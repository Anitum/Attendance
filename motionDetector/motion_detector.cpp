#include <opencv2/opencv.hpp>
#include <iostream>
#include <chrono>
#include <regex>
#include <thread>
#include <atomic>
#include <string>
#include <set>
#include <iomanip>
#include <map>

// Global variables for general motion detection
const int GENERAL_BLUR_SIZE = 15;
const int GENERAL_THRESHOLD_VALUE = 25;
const int GENERAL_MIN_CONTOUR_AREA = 50;
const int SKIP_FRAMES = 10;

// Common variables
const int RESIZE_WIDTH = 320;
const int RESIZE_HEIGHT = 240;

// Forward declaration of helper function
std::string getCurrentTimestamp();


// Helper functions
inline std::string extractChannelNumber(const std::string& filename) {
    std::regex channelRegex("channel(10|[1-9])");
    std::smatch match;
    if (std::regex_search(filename, match, channelRegex)) {
        return match[1].str();
    }
    return "unknown";
}

inline bool isValidChannel(const std::string& channelNum) {
    static const std::set<std::string> validChannels = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"};
    return validChannels.find(channelNum) != validChannels.end();
}

// Detection function
bool detectGeneralMotion(cv::VideoCapture& cap) {
    cv::Mat frame, resizedFrame, gray, blurFrame, diffFrame, threshFrame, prevFrame;
    bool motionDetected = false;
    int frameCount = 0;

    while (true) {
        cap >> frame;
        if (frame.empty() || motionDetected) break;
        
        if (frameCount++ % SKIP_FRAMES != 0) continue;

        cv::resize(frame, resizedFrame, cv::Size(RESIZE_WIDTH, RESIZE_HEIGHT));
        cv::cvtColor(resizedFrame, gray, cv::COLOR_BGR2GRAY);

        cv::Rect timestampArea(0, 0, RESIZE_WIDTH * 0.36, RESIZE_HEIGHT * 0.072);
        gray(timestampArea).setTo(0);

        cv::blur(gray, blurFrame, cv::Size(GENERAL_BLUR_SIZE | 1, GENERAL_BLUR_SIZE | 1));

        if (prevFrame.empty()) {
            blurFrame.copyTo(prevFrame);
            continue;
        }

        cv::absdiff(prevFrame, blurFrame, diffFrame);
        cv::threshold(diffFrame, threshFrame, GENERAL_THRESHOLD_VALUE, 255, cv::THRESH_BINARY);

        cv::Mat labels, stats, centroids;
        cv::connectedComponentsWithStats(threshFrame, labels, stats, centroids);

        for (int i = 1; i < stats.rows; ++i) {
            if (stats.at<int>(i, cv::CC_STAT_AREA) >= GENERAL_MIN_CONTOUR_AREA) {
                motionDetected = true;
                break;
            }
        }

        if (motionDetected) break;
        blurFrame.copyTo(prevFrame);
    }

    return motionDetected;
}

std::string getCurrentTimestamp() {
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&in_time_t), "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <video_file>" << std::endl;
        return -1;
    }

    std::string videoPath = argv[1];
    std::string channel = extractChannelNumber(videoPath);
    
    if (!isValidChannel(channel)) {
        std::cerr << "Invalid filename. Video file must be named 'channel' followed by a number (1-10)" << std::endl;
        return -1;
    }

    cv::VideoCapture cap(videoPath);
    if (!cap.isOpened()) {
        std::cerr << "Cannot open video file. Check format or path." << std::endl;
        return -1;
    }

    bool generalMotion = detectGeneralMotion(cap);

    // Simple output format without timestamps
    std::cout << "[" 
              << "channel" + channel << ", "
              << (generalMotion ? "True" : "False") << ", "
              << getCurrentTimestamp() << "]" << std::endl;

    return 0;
}
// compile with g++ -std=c++11 -o motion_detector motion_detector.cpp $(pkg-config --cflags --libs opencv4) -pthread