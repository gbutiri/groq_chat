CREATE TABLE `groq_conversations` (
  `conv_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `conv_type_id` int(11) NOT NULL DEFAULT 0,
  `conv_summary` text NOT NULL,
  `conv_first_msg` datetime DEFAULT NULL,
  `conv_last_msg` datetime DEFAULT NULL,
  `conv_created` timestamp NOT NULL DEFAULT current_timestamp(),
  `conv_updated` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`conv_id`)
)

CREATE TABLE `groq_messages` (
  `msg_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `conv_id` bigint(20) unsigned NOT NULL DEFAULT 0,
  `msg_role` varchar(32) NOT NULL,
  `msg_content` text NOT NULL,
  `msg_tool_name` varchar(255) NOT NULL DEFAULT '',
  `msg_tool_id` varchar(255) NOT NULL DEFAULT '',
  `msg_f_name` varchar(255) NOT NULL DEFAULT '',
  `msg_created` timestamp NOT NULL DEFAULT current_timestamp(),
  `msg_updated` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`msg_id`)
)

CREATE TABLE `groq_conv_types` (
  `conv_type_id` int(11) unsigned NOT NULL DEFAULT 0,
  `conv_type_name` varchar(20) NOT NULL DEFAULT '',
  `conv_type_color` varchar(10) NOT NULL DEFAULT '',
  PRIMARY KEY (`conv_type_id`)
)