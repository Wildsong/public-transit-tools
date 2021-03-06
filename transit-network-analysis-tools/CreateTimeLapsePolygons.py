################################################################################
## Toolbox: Transit Network Analysis Tools
## Tool name: Prepare Time Lapse Polygons
## Created by: Melinda Morang, Esri
## Last updated: 17 June 2019
################################################################################
'''Run a Service Area analysis incrementing the time of day. Save the polygons 
to a feature class that can be used to generate a time lapse video.'''
################################################################################
'''Copyright 2019 Esri
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.'''
################################################################################

import os
import datetime
import arcpy
import AnalysisHelpers
arcpy.env.overwriteOutput = True

class CustomError(Exception):
    pass

def runTool(input_network_analyst_layer, output_feature_class, start_day_input="Wednesday", start_time_input="08:00",
            end_day_input="Wednesday", end_time_input="09:00", increment_input=1):
    """Iteratively calculate Service Area polygons for each time increment within a time window.
    
    Creates an output polygon feature class contain one row per Service Area per time of day solved.

    Parameters: 
    input_network_analyst_layer: A ready-to-solve Service Area layer in your map or saved as a layer file.
    output_feature_class: The output feature class.
    start_day_input: Day of the week or YYYYMMDD date for the first start time of your analysis.
    start_time_input: The lower end of the time window you wish to analyze. Must be in HH:MM format (24-hour time). For
        example, 2 AM is 02:00, and 2 PM is 14:00.
    end_day_input:  If you're using a generic weekday for start_day_input, you must use the same day. If you want to run
        an analysis spanning multiple days, choose specific YYYYMMDD dates for both start_day_input and end_day_input.
    end_time_input: The upper end of the time window you wish to analyze. Must be in HH:MM format (24-hour time). The
        end_time_input is inclusive, meaning that a Service Area polygon will be included in the results for the time of
        day you enter here.
    increment_input: Increment the Service Area's time of day by this amount between solves (in minutes). For example,
        for a Time Increment of 1 minute, the results may include a Service Area polygon for 10:00, 10:01, 10:02, etc. A
            increment_input of 2 minutes would generate Service Area polygons for 10:00, 10:02, 10:04, etc.

    """

    try:

        #Check out the Network Analyst extension license
        if arcpy.CheckExtension("Network") == "Available":
            arcpy.CheckOutExtension("Network")
        else:
            arcpy.AddError("You must have a Network Analyst license to use this tool.")
            raise CustomError

        # ----- Get and process inputs -----

        # Service Area from the map that is ready to solve with all the desired settings
        # (except time of day - we'll adjust that in this script)
        desc = arcpy.Describe(input_network_analyst_layer)
        if desc.dataType != "NALayer" or desc.solverName != "Service Area Solver":
            arcpy.AddError("Input layer must be a Service Area layer.")
            raise CustomError

        # Make list of times of day to run the analysis
        try:
            timelist = AnalysisHelpers.make_analysis_time_of_day_list(
                start_day_input, end_day_input, start_time_input, end_time_input, increment_input)
        except Exception as ex:
            arcpy.AddError(ex)
            raise CustomError

        # If the input NA layer is a layer file, convert it to a layer object
        if not AnalysisHelpers.isPy3:
            if isinstance(input_network_analyst_layer, (unicode, str)) and input_network_analyst_layer.endswith(".lyr"):
                input_network_analyst_layer = arcpy.mapping.Layer(input_network_analyst_layer)
        else:
            if isinstance(input_network_analyst_layer, str) and input_network_analyst_layer.endswith(".lyrx"):
                input_network_analyst_layer = arcpy.mp.LayerFile(input_network_analyst_layer).listLayers()[0]

        
        # ----- Add a TimeOfDay field to SA Polygons -----

        # Grab the polygons sublayer, which we will export after each solve.
        sublayer_names = arcpy.na.GetNAClassNames(input_network_analyst_layer) # To ensure compatibility with localized software
        if not AnalysisHelpers.isPy3:
            polygons_subLayer = arcpy.mapping.ListLayers(input_network_analyst_layer, sublayer_names["SAPolygons"])[0]
        else:
            polygons_subLayer = input_network_analyst_layer.listLayers(sublayer_names["SAPolygons"])[0]

        # Add the TimeOfDay field
        time_field = AnalysisHelpers.add_TimeOfDay_field_to_sublayer(
            input_network_analyst_layer,
            polygons_subLayer,
            sublayer_names["SAPolygons"]
            )

        # ----- Solve NA layer in a loop for each time of day -----

        # Grab the solver properties object from the NA layer so we can set the time of day
        solverProps = arcpy.na.GetSolverProperties(input_network_analyst_layer)

        # Solve for each time of day and save output
        arcpy.AddMessage("Solving Service Area at time...")
        first = True
        for t in timelist:
            arcpy.AddMessage(str(t))
            
            # Switch the time of day
            solverProps.timeOfDay = t
            
            # Solve the Service Area
            try:
                arcpy.na.Solve(input_network_analyst_layer)
            except:
                arcpy.AddError("Solve failed.")
                arcpy.AddError(arcpy.GetMessages(2))
                raise CustomError
            
            # Calculate the TimeOfDay field
            AnalysisHelpers.calculate_TimeOfDay_field(polygons_subLayer, time_field, t)
            
            #Append the polygons to the output feature class. If this was the first
            #solve, create the feature class.
            if first:
                arcpy.conversion.FeatureClassToFeatureClass(
                    polygons_subLayer,
                    os.path.dirname(output_feature_class),
                    os.path.basename(output_feature_class)
                    )
            else:
                arcpy.management.Append(polygons_subLayer, output_feature_class)
            first = False

    except CustomError:
        pass
    except:
        raise
