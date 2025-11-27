#include <gtest/gtest.h>
#include "Route.h"
#include <string>
#include <fstream>
#include <cstdio>

TEST(RouteTest, LoadFromStringBasic) {
    Route r;
    std::string payload = R"(
# example route
10 20 1.5
30 40
50 60 2.0
)";
    EXPECT_TRUE(r.loadFromString(payload));
    EXPECT_EQ(r.size(), 3);
    EXPECT_DOUBLE_EQ(r[0].x, 10.0);
    EXPECT_DOUBLE_EQ(r[0].y, 20.0);
    EXPECT_DOUBLE_EQ(r[0].speed, 1.5);
    EXPECT_DOUBLE_EQ(r[1].speed, 0.0);
}

TEST(RouteTest, SaveAndLoadFile) {
    Route r;
    r.addWaypoint(Waypoint(1.0,2.0,0.5));
    r.addWaypoint(Waypoint(3.0,4.0,1.0));
    std::string tmp = "tests_tmp.route";
    EXPECT_TRUE(r.saveToFile(tmp));

    Route r2;
    EXPECT_TRUE(r2.loadFromFile(tmp));
    EXPECT_EQ(r2.size(), 2);
    EXPECT_DOUBLE_EQ(r2[1].x, 3.0);
    EXPECT_DOUBLE_EQ(r2[1].y, 4.0);
    // cleanup
    std::remove(tmp.c_str());
}

TEST(RouteTest, ClearAndAdd) {
    Route r;
    r.addWaypoint(Waypoint(0,0));
    r.addWaypoint(Waypoint(1,1));
    EXPECT_EQ(r.size(), 2);
    r.clear();
    EXPECT_EQ(r.size(), 0);
    r.addWaypoint(Waypoint(5,6,0.2));
    EXPECT_EQ(r.size(), 1);
    EXPECT_DOUBLE_EQ(r[0].x, 5.0);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}



